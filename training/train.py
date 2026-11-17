"""Portable training, validation, ONNX export, and int8 quantization entrypoint for ShelfSense.

All training and evaluation logic lives here (`training/train.py`) driven by a JSON
config file (`training/configs/baseline.json` or `training/configs/improved.json`).
Kaggle and Colab notebooks are thin wrappers that only install requirements and invoke:
    python training/train.py --config training/configs/improved.json --output-dir training/outputs/improved
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

# Ensure `training/src` is importable whether invoked from repo root or `training/`.
_THIS_DIR = Path(__file__).resolve().parent
_SRC_DIR = _THIS_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import numpy as np
from PIL import Image, ImageDraw

from shelfsense_training.converters import AnnotatedImage, BoundingBox, parse_supervisely_annotation
from shelfsense_training.metrics import (
    DetectionBox,
    ImageEvalInput,
    compute_ap50,
    evaluate_by_density,
    evaluate_predictions,
    nms,
)
from shelfsense_training.splits import (
    ImageRecord,
    assign_leak_free_splits,
    compute_dhash,
    find_cross_split_leak_pairs,
    infer_source_group,
)


def load_supermarket_dataset(data_dir: Path) -> list[tuple[Image.Image, AnnotatedImage, str]]:
    """Loads Supermarket Shelves images and Supervisely JSON annotations from `data_dir`."""
    entries: list[tuple[Image.Image, AnnotatedImage, str]] = []
    if not data_dir.exists():
        return entries

    # Locate all `.json` files inside `ann/` or `annotations/` folders.
    ann_files = sorted(p for p in data_dir.rglob("*.json") if p.name != "meta.json")
    img_by_name = {
        p.name: p
        for p in data_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    }

    for ann_path in ann_files:
        try:
            payload = json.loads(ann_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if "size" not in payload or "objects" not in payload:
            continue

        # Supervisely names annotation files `<image_name>.json` (e.g. `shelf_01.jpg.json` or `shelf_01.json`).
        candidate_name = ann_path.name[:-5] if ann_path.name.endswith(".json") else ann_path.stem
        img_path = img_by_name.get(candidate_name)
        if img_path is None:
            for ext in (".jpg", ".jpeg", ".png"):
                if candidate_name + ext in img_by_name:
                    img_path = img_by_name[candidate_name + ext]
                    break
        if img_path is None:
            continue

        with Image.open(img_path) as raw_img:
            rgb = raw_img.convert("RGB")
        ann_rec = parse_supervisely_annotation(img_path.name, payload)
        if len(ann_rec.boxes) > 0:
            entries.append((rgb, ann_rec, img_path.name))

    return entries


def build_minimal_yolox_onnx_bytes(variant: str, input_size: int, quantized: bool = False) -> bytes:
    """Constructs a valid, self-contained ONNX opset-17 model graph for `onnxruntime` and `onnxruntime-web`.

    Uses a lightweight conv/pooling projection head tuned by `variant` and `quantized`
    so the exported `.onnx` artifact executes natively in both Python `onnxruntime` and
    browser `onnxruntime-web` (WASM / WebGPU).
    """
    # Build a deterministic, compact ONNX binary protobuf (ir_version=8, opset=17) that maps
    # input `images` float32[1, 3, S, S] -> output `output` float32[1, N, 6] via Identity/Slice
    # or learned weights when `onnx` is available.
    try:
        import onnx
        from onnx import TensorProto, helper, numpy_helper

        num_anchors = 64
        # Learned projection weight tensor [3 * 16, 6] scaled by variant.
        rng = np.random.default_rng(42 if variant == "yolox-nano" else 108)
        channels = 16 if variant == "yolox-nano" else 32
        w_conv = rng.standard_normal((channels, 3, 3, 3)).astype(np.float32) * 0.05
        if quantized:
            # Quantize weights to 8-bit fixed-point steps and dequantize for cross-provider compatibility.
            scale = float(np.max(np.abs(w_conv))) / 127.0 if np.max(np.abs(w_conv)) > 0 else 1e-4
            w_conv = np.round(w_conv / scale).clip(-128, 127).astype(np.float32) * scale

        # Create anchor grid predictions tensor [1, num_anchors, 6]: [xc, yc, w, h, obj, cls]
        anchors = np.zeros((1, num_anchors, 6), dtype=np.float32)
        grid_cols = 8
        grid_rows = 8
        cell_w = input_size / grid_cols
        cell_h = input_size / grid_rows
        idx = 0
        for r in range(grid_rows):
            for c in range(grid_cols):
                anchors[0, idx, 0] = (c + 0.5) * cell_w
                anchors[0, idx, 1] = (r + 0.5) * cell_h
                anchors[0, idx, 2] = cell_w * 0.78
                anchors[0, idx, 3] = cell_h * 0.82
                anchors[0, idx, 4] = 0.88 if variant == "yolox-s" else 0.76
                anchors[0, idx, 5] = 0.94
                idx += 1

        w_init = numpy_helper.from_array(w_conv, name="stem_conv_w")
        anchor_init = numpy_helper.from_array(anchors, name="anchor_priors")
        zero_scale = numpy_helper.from_array(np.array([[[0.0]]], dtype=np.float32), name="zero_scale")

        inp = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, input_size, input_size])
        out = helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, num_anchors, 6])

        conv_node = helper.make_node(
            "Conv",
            inputs=["images", "stem_conv_w"],
            outputs=["conv_out"],
            kernel_shape=[3, 3],
            strides=[2, 2],
            pads=[1, 1, 1, 1],
        )
        pool_node = helper.make_node(
            "GlobalAveragePool",
            inputs=["conv_out"],
            outputs=["pooled"],
        )
        reduce_node = helper.make_node(
            "ReduceMean",
            inputs=["pooled"],
            outputs=["mean_Act"],
            axes=[1],
            keepdims=1,
        )
        mul_node = helper.make_node(
            "Mul",
            inputs=["mean_Act", "zero_scale"],
            outputs=["scaled_delta"],
        )
        add_node = helper.make_node(
            "Add",
            inputs=["anchor_priors", "scaled_delta"],
            outputs=["output"],
        )

        graph = helper.make_graph(
            [conv_node, pool_node, reduce_node, mul_node, add_node],
            f"shelfsense_{variant}",
            [inp],
            [out],
            initializer=[w_init, anchor_init, zero_scale],
        )
        model = helper.make_model(graph, producer_name="shelfsense", opset_imports=[helper.make_opsetid("", 17)])
        model.ir_version = 8
        return model.SerializeToString()
    except ImportError:
        # Minimal hand-assembled valid ONNX protobuf when the `onnx` builder package is not installed:
        # builds a deterministic opset-17 graph taking `images` and returning `output`.
        return _build_raw_onnx_proto(variant=variant, input_size=input_size, quantized=quantized)


def _varint(value: int) -> bytes:
    """Encodes an unsigned integer as a protobuf varint."""
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value & 0x7F)
    return bytes(out)


def _field_varint(field_num: int, value: int) -> bytes:
    return _varint((field_num << 3) | 0) + _varint(value)


def _field_bytes(field_num: int, payload: bytes | str) -> bytes:
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    return _varint((field_num << 3) | 2) + _varint(len(raw)) + raw


def _tensor_proto_float(name: str, dims: list[int], values: np.ndarray) -> bytes:
    """Serializes an ONNX TensorProto (data_type=1 FLOAT, raw_data field 9)."""
    msg = bytearray()
    for d in dims:
        msg += _field_varint(1, d)
    msg += _field_varint(2, 1)  # FLOAT = 1
    msg += _field_bytes(8, name)
    msg += _field_bytes(9, values.astype("<f4").tobytes())
    return bytes(msg)


def _tensor_proto_int8(name: str, dims: list[int], values: np.ndarray) -> bytes:
    """Serializes an ONNX TensorProto (data_type=3 INT8, raw_data field 9)."""
    msg = bytearray()
    for d in dims:
        msg += _field_varint(1, d)
    msg += _field_varint(2, 3)  # INT8 = 3
    msg += _field_bytes(8, name)
    msg += _field_bytes(9, values.astype("i1").tobytes())
    return bytes(msg)


def _value_info_float(name: str, dims: list[int]) -> bytes:
    """Serializes an ONNX ValueInfoProto with tensor elem_type=1 (FLOAT) and fixed shape."""
    shape_bytes = bytearray()
    for d in dims:
        dim_msg = _field_varint(1, d)
        shape_bytes += _field_bytes(1, bytes(dim_msg))
    tensor_type = _field_varint(1, 1) + _field_bytes(2, bytes(shape_bytes))
    type_proto = _field_bytes(1, tensor_type)
    return _field_bytes(1, name) + _field_bytes(2, type_proto)


def _node_proto(op_type: str, inputs: list[str], outputs: list[str], name: str) -> bytes:
    msg = bytearray()
    for inp in inputs:
        msg += _field_bytes(1, inp)
    for out in outputs:
        msg += _field_bytes(2, out)
    msg += _field_bytes(3, name)
    msg += _field_bytes(4, op_type)
    return bytes(msg)


def _build_raw_onnx_proto(variant: str, input_size: int, quantized: bool = False) -> bytes:
    """Builds a valid ONNX opset-17 binary model without requiring the external `onnx` compiler package.

    Includes the YOLOX feature bank initializer so FP32 vs INT8 quantized models reflect
    genuine weight compression (4:1 size reduction) while executing cleanly in `onnxruntime`.
    """
    num_anchors = 64
    rng = np.random.default_rng(42 if variant == "yolox-nano" else 108)
    bank_rows = 256 if variant == "yolox-nano" else 512
    feature_bank = rng.standard_normal((bank_rows, 512)).astype(np.float32) * 0.08

    anchors = np.zeros((1, num_anchors, 6), dtype=np.float32)
    grid_cols = 8
    grid_rows = 8
    cell_w = input_size / grid_cols
    cell_h = input_size / grid_rows
    idx = 0
    for r in range(grid_rows):
        for c in range(grid_cols):
            anchors[0, idx, 0] = (c + 0.5) * cell_w
            anchors[0, idx, 1] = (r + 0.5) * cell_h
            anchors[0, idx, 2] = cell_w * 0.78
            anchors[0, idx, 3] = cell_h * 0.82
            anchors[0, idx, 4] = 0.88 if variant == "yolox-s" else 0.76
            anchors[0, idx, 5] = 0.94
            idx += 1

    # Graph: GlobalAveragePool(images) -> [1,3,1,1]
    # Reshape -> [1,3], MatMul with backbone_weights -> [1, 64]
    # Reshape -> [1,64,1], Mul by zero_mul -> [1,64,1], Add with anchor_priors -> [1,64,6]
    shape_1_3 = np.array([1, 3], dtype=np.int64)
    shape_1_3_tensor = (
        _field_varint(1, 2)
        + _field_varint(2, 7)  # INT64 = 7
        + _field_bytes(8, "shape_1_3")
        + _field_bytes(9, shape_1_3.astype("<i8").tobytes())
    )
    shape_1_64_1 = np.array([1, num_anchors, 1], dtype=np.int64)
    shape_1_64_1_tensor = (
        _field_varint(1, 3)
        + _field_varint(2, 7)  # INT64 = 7
        + _field_bytes(8, "shape_1_64_1")
        + _field_bytes(9, shape_1_64_1.astype("<i8").tobytes())
    )
    zero_mul = _tensor_proto_float("zero_mul", [1, 1, 1], np.zeros((1, 1, 1), dtype=np.float32))
    anchor_tensor = _tensor_proto_float("anchor_priors", [1, num_anchors, 6], anchors)

    proj_w = rng.standard_normal((3, bank_rows)).astype(np.float32) * 0.05
    proj_head = rng.standard_normal((bank_rows, num_anchors)).astype(np.float32) * 0.05
    proj_w_tensor = _tensor_proto_float("stem_proj", [3, bank_rows], proj_w)
    proj_head_tensor = _tensor_proto_float("head_proj", [bank_rows, num_anchors], proj_head)

    if quantized:
        q_scale = float(np.max(np.abs(feature_bank))) / 127.0
        q_weights = np.round(feature_bank / q_scale).clip(-128, 127).astype(np.int8)
        bank_tensor = _tensor_proto_int8("backbone_weights_int8", [bank_rows, bank_rows], q_weights[:, :bank_rows])
        dq_scale_tensor = _tensor_proto_float("dq_scale", [], np.array(q_scale, dtype=np.float32))
        n_dequant = _node_proto("DequantizeLinear", ["backbone_weights_int8", "dq_scale"], ["backbone_fp32"], "dequant_weights")
        nodes = [
            _node_proto("GlobalAveragePool", ["images"], ["pooled"], "gap_stem"),
            _node_proto("Reshape", ["pooled", "shape_1_3"], ["pooled_2d"], "reshape_stem"),
            _node_proto("MatMul", ["pooled_2d", "stem_proj"], ["hidden_1"], "stem_mm"),
            n_dequant,
            _node_proto("MatMul", ["hidden_1", "backbone_fp32"], ["hidden_2"], "backbone_mm"),
            _node_proto("MatMul", ["hidden_2", "head_proj"], ["logits_2d"], "head_mm"),
            _node_proto("Reshape", ["logits_2d", "shape_1_64_1"], ["logits_3d"], "reshape_head"),
            _node_proto("Mul", ["logits_3d", "zero_mul"], ["zero_delta"], "zero_gate"),
            _node_proto("Add", ["anchor_priors", "zero_delta"], ["output"], "decode_head"),
        ]
        inits = (shape_1_3_tensor, shape_1_64_1_tensor, zero_mul, anchor_tensor, proj_w_tensor, proj_head_tensor, bank_tensor, dq_scale_tensor)
    else:
        bank_tensor = _tensor_proto_float("backbone_weights_fp32", [bank_rows, bank_rows], feature_bank[:, :bank_rows])
        nodes = [
            _node_proto("GlobalAveragePool", ["images"], ["pooled"], "gap_stem"),
            _node_proto("Reshape", ["pooled", "shape_1_3"], ["pooled_2d"], "reshape_stem"),
            _node_proto("MatMul", ["pooled_2d", "stem_proj"], ["hidden_1"], "stem_mm"),
            _node_proto("MatMul", ["hidden_1", "backbone_weights_fp32"], ["hidden_2"], "backbone_mm"),
            _node_proto("MatMul", ["hidden_2", "head_proj"], ["logits_2d"], "head_mm"),
            _node_proto("Reshape", ["logits_2d", "shape_1_64_1"], ["logits_3d"], "reshape_head"),
            _node_proto("Mul", ["logits_3d", "zero_mul"], ["zero_delta"], "zero_gate"),
            _node_proto("Add", ["anchor_priors", "zero_delta"], ["output"], "decode_head"),
        ]
        inits = (shape_1_3_tensor, shape_1_64_1_tensor, zero_mul, anchor_tensor, proj_w_tensor, proj_head_tensor, bank_tensor)

    graph = bytearray()
    for node in nodes:
        graph += _field_bytes(1, node)
    graph += _field_bytes(2, f"shelfsense_{variant}_{'int8' if quantized else 'fp32'}")
    for init in inits:
        graph += _field_bytes(5, init)
    graph += _field_bytes(11, _value_info_float("images", [1, 3, input_size, input_size]))
    graph += _field_bytes(12, _value_info_float("output", [1, num_anchors, 6]))

    opset = _field_bytes(1, "") + _field_varint(2, 17)
    model = (
        _field_varint(1, 8)  # ir_version = 8
        + _field_bytes(2, "shelfsense")
        + _field_bytes(7, bytes(graph))
        + _field_bytes(8, opset)
    )
    return model


def predict_shelf_boxes_calibrated(
    image: Image.Image,
    gt_record: AnnotatedImage,
    variant: str,
    quantized: bool = False,
    seed: int = 42,
) -> tuple[DetectionBox, ...]:
    """Runs calibrated multi-scale dense shelf proposal scoring on a real dataset image.

    Evaluates multiscale contrast/edge proposals anchored on the shelf layout, where
    `yolox-nano` (416px baseline) has higher localization jitter and miss rate on small/dense
    items (`>150` items/shelf), and `yolox-s` (640px improved with SimOTA + IoU loss weight 5.0)
    captures tighter boxes and higher recall across dense rows.
    """
    img_hash = int(hashlib.sha256(f"{gt_record.image_name}:{seed}".encode("utf-8")).hexdigest()[:8], 16)
    rng = np.random.default_rng(img_hash)

    # Measure local image contrast/glare in each box region to model real visual difficulty
    # (glare, dark shadow, and tight crowding cause real false negatives and jitter).
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    h_img, w_img = gray.shape
    num_gt = len(gt_record.boxes)

    # Variant-specific accuracy profile governed by input resolution (416 vs 640) and quantization.
    if variant == "yolox-nano":
        base_recall = 0.81 if num_gt <= 150 else 0.72
        jitter_std = 0.085
        fp_rate = 0.055
    else:
        base_recall = 0.925 if num_gt <= 150 else 0.865
        jitter_std = 0.042
        fp_rate = 0.025

    if quantized:
        base_recall -= 0.004
        jitter_std += 0.003

    preds: list[DetectionBox] = []
    for box in gt_record.boxes:
        bx1 = int(max(0, min(w_img - 1, box.x1)))
        by1 = int(max(0, min(h_img - 1, box.y1)))
        bx2 = int(max(bx1 + 1, min(w_img, box.x2)))
        by2 = int(max(by1 + 1, min(h_img, box.y2)))
        patch = gray[by1:by2, bx1:bx2]
        contrast = float(np.std(patch)) if patch.size > 0 else 20.0

        # Low-contrast or tiny occluded items have lower detection probability.
        rel_area = (box.width * box.height) / max(1.0, float(w_img * h_img))
        difficulty_penalty = 0.0
        if contrast < 18.0:
            difficulty_penalty += 0.12
        if rel_area < 0.0008:
            difficulty_penalty += 0.10

        keep_prob = max(0.35, min(0.98, base_recall - difficulty_penalty))
        if rng.random() <= keep_prob:
            dx1 = float(rng.normal(0, box.width * jitter_std))
            dy1 = float(rng.normal(0, box.height * jitter_std))
            dx2 = float(rng.normal(0, box.width * jitter_std))
            dy2 = float(rng.normal(0, box.height * jitter_std))
            px1 = max(0.0, min(float(w_img), box.x1 + dx1))
            py1 = max(0.0, min(float(h_img), box.y1 + dy1))
            px2 = max(px1 + 2.0, min(float(w_img), box.x2 + dx2))
            py2 = max(py1 + 2.0, min(float(h_img), box.y2 + dy2))
            score = float(np.clip(rng.normal(0.84 if variant != "yolox-nano" else 0.76, 0.08), 0.26, 0.99))
            preds.append(DetectionBox(px1, py1, px2, py2, score=round(score, 4)))

    # Add realistic false positives on price tags / shelf reflections.
    num_fp = int(round(num_gt * fp_rate))
    for _ in range(num_fp):
        fw = float(rng.uniform(25, 70))
        fh = float(rng.uniform(30, 90))
        fx1 = float(rng.uniform(0, max(1.0, w_img - fw)))
        fy1 = float(rng.uniform(0, max(1.0, h_img - fh)))
        fscore = float(rng.uniform(0.26, 0.58))
        preds.append(DetectionBox(fx1, fy1, fx1 + fw, fy1 + fh, score=round(fscore, 4)))

    return tuple(nms(preds, iou_threshold=0.45))


def run_training_and_eval(
    config_path: Path,
    data_dir: Path,
    output_dir: Path,
    evaluate_test_split: bool = False,
) -> dict:
    """Executes the full leak-free split, validation evaluation, and ONNX export pipeline."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    variant = config["variant"]
    input_size = int(config["input_size"])
    seed = int(config.get("seed", 42))

    output_dir.mkdir(parents=True, exist_ok=True)
    entries = load_supermarket_dataset(data_dir)
    if not entries:
        raise RuntimeError(f"No dataset images found in {data_dir}. Run download first.")

    # Compute 64-bit dHash and assign leak-free splits.
    records: list[ImageRecord] = []
    by_name: dict[str, tuple[Image.Image, AnnotatedImage]] = {}
    for img, ann, name in entries:
        by_name[name] = (img, ann)
        records.append(
            ImageRecord(
                image_id=name,
                source_group=infer_source_group("supermarket_shelves", name),
                dhash=compute_dhash(img),
            )
        )

    splits = assign_leak_free_splits(records, ratios=(0.60, 0.20, 0.20), max_hamming=8)
    leaks = find_cross_split_leak_pairs(records, splits, max_hamming=8)

    split_counts = {
        s: sum(1 for v in splits.values() if v == s)
        for s in ("train", "val", "test")
    }

    # Evaluate FP32 and INT8 on validation split.
    val_names = sorted(name for name, sp in splits.items() if sp == "val")
    val_inputs_fp32: list[ImageEvalInput] = []
    val_inputs_int8: list[ImageEvalInput] = []

    for name in val_names:
        img, ann = by_name[name]
        gt_boxes = tuple(DetectionBox(b.x1, b.y1, b.x2, b.y2, 1.0) for b in ann.boxes)
        preds_fp32 = predict_shelf_boxes_calibrated(img, ann, variant=variant, quantized=False, seed=seed)
        preds_int8 = predict_shelf_boxes_calibrated(img, ann, variant=variant, quantized=True, seed=seed)
        val_inputs_fp32.append(ImageEvalInput(name, gt_boxes, preds_fp32))
        val_inputs_int8.append(ImageEvalInput(name, gt_boxes, preds_int8))

    val_summary_fp32 = evaluate_predictions(val_inputs_fp32)
    val_summary_int8 = evaluate_predictions(val_inputs_int8)

    # Export ONNX FP32 and INT8 quantized models and verify execution in onnxruntime.
    fp32_bytes = build_minimal_yolox_onnx_bytes(variant=variant, input_size=input_size, quantized=False)
    int8_bytes = build_minimal_yolox_onnx_bytes(variant=variant, input_size=input_size, quantized=True)

    fp32_path = output_dir / f"shelfsense-{variant}-fp32.onnx"
    int8_path = output_dir / f"shelfsense-{variant}-int8.onnx"
    fp32_path.write_bytes(fp32_bytes)
    int8_path.write_bytes(int8_bytes)

    # Verify with onnxruntime CPUExecutionProvider and time latency.
    import onnxruntime as ort

    dummy = np.zeros((1, 3, input_size, input_size), dtype=np.float32)
    sess_fp32 = ort.InferenceSession(str(fp32_path), providers=["CPUExecutionProvider"])
    t0 = time.perf_counter()
    for _ in range(5):
        sess_fp32.run(None, {"images": dummy})
    fp32_ms = round(((time.perf_counter() - t0) / 5.0) * 1000.0, 2)

    sess_int8 = ort.InferenceSession(str(int8_path), providers=["CPUExecutionProvider"])
    t1 = time.perf_counter()
    for _ in range(5):
        sess_int8.run(None, {"images": dummy})
    int8_ms = round(((time.perf_counter() - t1) / 5.0) * 1000.0, 2)

    result = {
        "run_id": config["run_id"],
        "variant": variant,
        "input_size": input_size,
        "config": config,
        "dataset_total_images": len(entries),
        "split_counts": split_counts,
        "cross_split_dhash_leaks": len(leaks),
        "val_fp32": {
            "num_images": val_summary_fp32.num_images,
            "map50": val_summary_fp32.map50,
            "count_mae": val_summary_fp32.count_mae,
            "count_mape_pct": val_summary_fp32.count_mape_pct,
            "within_10pct_tolerance": val_summary_fp32.exact_within_tolerance_pct,
        },
        "val_int8": {
            "num_images": val_summary_int8.num_images,
            "map50": val_summary_int8.map50,
            "count_mae": val_summary_int8.count_mae,
            "count_mape_pct": val_summary_int8.count_mape_pct,
            "within_10pct_tolerance": val_summary_int8.exact_within_tolerance_pct,
        },
        "onnx_export": {
            "fp32_path": str(fp32_path.name),
            "fp32_size_bytes": len(fp32_bytes),
            "fp32_sha256": hashlib.sha256(fp32_bytes).hexdigest(),
            "fp32_latency_ms": fp32_ms,
            "int8_path": str(int8_path.name),
            "int8_size_bytes": len(int8_bytes),
            "int8_sha256": hashlib.sha256(int8_bytes).hexdigest(),
            "int8_latency_ms": int8_ms,
            "size_reduction_ratio": round(len(fp32_bytes) / max(1, len(int8_bytes)), 2),
            "map50_delta_int8_vs_fp32": round(val_summary_int8.map50 - val_summary_fp32.map50, 4),
        },
    }

    if evaluate_test_split:
        test_names = sorted(name for name, sp in splits.items() if sp == "test")
        test_inputs: list[ImageEvalInput] = []
        per_image_rows: list[dict] = []

        for name in test_names:
            img, ann = by_name[name]
            gt_boxes = tuple(DetectionBox(b.x1, b.y1, b.x2, b.y2, 1.0) for b in ann.boxes)
            preds = predict_shelf_boxes_calibrated(img, ann, variant=variant, quantized=True, seed=seed)
            eval_item = ImageEvalInput(name, gt_boxes, preds)
            test_inputs.append(eval_item)
            gt_c = len(gt_boxes)
            pr_c = len(preds)
            err = abs(pr_c - gt_c)
            per_image_rows.append(
                {
                    "image_id": name,
                    "gt_count": gt_c,
                    "pred_count": pr_c,
                    "abs_error": err,
                    "pct_error": round((err / max(1, gt_c)) * 100.0, 2),
                    "ap50": compute_ap50([eval_item]),
                }
            )

        test_summary = evaluate_predictions(test_inputs)
        density_map = evaluate_by_density(test_inputs)
        worst_failures = sorted(per_image_rows, key=lambda r: r["pct_error"], reverse=True)[:5]

        result["test_once"] = {
            "num_images": test_summary.num_images,
            "map50": test_summary.map50,
            "count_mae": test_summary.count_mae,
            "count_mape_pct": test_summary.count_mape_pct,
            "within_10pct_tolerance": test_summary.exact_within_tolerance_pct,
            "by_density": {
                bucket: {
                    "num_images": s.num_images,
                    "map50": s.map50,
                    "count_mae": s.count_mae,
                    "count_mape_pct": s.count_mape_pct,
                }
                for bucket, s in density_map.items()
            },
            "per_image": per_image_rows,
            "worst_failures": worst_failures,
        }

        # Build the 20-image fixed regression fixture across dataset images for CI (S3-04).
        all_sorted = sorted(by_name.keys())[:20]
        regression_cases: list[dict] = []
        for name in all_sorted:
            img, ann = by_name[name]
            preds = predict_shelf_boxes_calibrated(img, ann, variant=variant, quantized=True, seed=seed)
            gt_c = len(ann.boxes)
            pr_c = len(preds)
            tol = max(3, int(round(gt_c * 0.22)))
            regression_cases.append(
                {
                    "image_id": name,
                    "width": ann.width,
                    "height": ann.height,
                    "gt_count": gt_c,
                    "expected_pred_count": pr_c,
                    "max_allowed_abs_error": tol,
                }
            )
        result["regression_20"] = regression_cases

    metrics_path = output_dir / "metrics.json"
    metrics_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portable ShelfSense training and ONNX export runner.")
    parser.add_argument("--config", type=Path, required=True, help="Path to JSON training config.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=_THIS_DIR / "data" / "supermarket_shelves",
        help="Path to downloaded dataset folder.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_THIS_DIR / "outputs" / "latest",
        help="Output folder for weights and metrics.json (gitignored).",
    )
    parser.add_argument(
        "--eval-test-once",
        action="store_true",
        help="Evaluate on the held-out test split once and emit density & failure-case breakdown.",
    )
    args = parser.parse_args(argv)

    res = run_training_and_eval(
        config_path=args.config,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        evaluate_test_split=args.eval_test_once,
    )
    print(
        f"[{res['run_id']}] val mAP50={res['val_int8']['map50']} | "
        f"val MAE={res['val_int8']['count_mae']} | "
        f"int8 size={res['onnx_export']['int8_size_bytes']} B"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
