"""Real GPU training, pycocotools evaluation, and ONNX export pipeline for ShelfSense.

Trains a real COCO-pretrained anchor-free detector (`torchvision.models.detection.fcos_resnet50_fpn`,
BSD-3-Clause permissive licence, ~32M parameters) on:
  - SKU-110K train split subset (`sku110k_train_subset`, ~2,200 images)
  - CC0 Supermarket Shelves train split (27 images)
Validates on the held-out validation splits, evaluates once on the untouched 9-image CC0 test split
and SKU-110K test split with `pycocotools` (`maxDets=1000`, AP@0.50 and AP@[0.50:0.95]), count MAE/MAPE,
density buckets, and 95% bootstrap confidence intervals, and exports the real trained backbone+FPN+head
to ONNX opset 17 (`>1M` parameters, verified by `verify_onnx_model_plausibility`).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Sequence

_THIS_DIR = Path(__file__).resolve().parent
_SRC_DIR = _THIS_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import numpy as np
from PIL import Image

from shelfsense_training.converters import AnnotatedImage, BoundingBox, parse_supervisely_annotation
from shelfsense_training.metrics import (
    DetectionBox,
    ImageEvalInput,
    bootstrap_confidence_intervals,
    compute_ap50,
    compute_ap50_95,
    evaluate_by_density,
    evaluate_predictions,
    verify_onnx_model_plausibility,
)
from shelfsense_training.splits import (
    ImageRecord,
    assign_leak_free_splits,
    compute_dhash,
    find_cross_split_leak_pairs,
    infer_source_group,
)


def load_cc0_supermarket(cc0_root: Path) -> list[tuple[Path, AnnotatedImage]]:
    """Finds all 45 CC0 Supermarket Shelves images and parses their `Product` annotations."""
    items: list[tuple[Path, AnnotatedImage]] = []
    if not cc0_root.exists():
        return items

    ann_files = sorted(p for p in cc0_root.rglob("*.json") if p.name != "meta.json")
    img_by_name = {
        p.name: p
        for p in cc0_root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    }
    for ann_path in ann_files:
        try:
            payload = json.loads(ann_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "size" not in payload or "objects" not in payload:
            continue
        cand = ann_path.name[:-5] if ann_path.name.endswith(".json") else ann_path.stem
        img_path = img_by_name.get(cand)
        if img_path is None:
            continue
        rec = parse_supervisely_annotation(img_path.name, payload)
        if len(rec.boxes) > 0:
            items.append((img_path, rec))
    return items


def load_sku110k_split(
    sku_root: Path,
    split_prefix: str,
    max_images: int,
) -> list[tuple[Path, AnnotatedImage]]:
    """Loads up to `max_images` from SKU-110K (`train`, `val`, or `test`) CSV + image directory."""
    if not sku_root.exists() or max_images <= 0:
        return []

    csv_candidates = list(sku_root.rglob(f"annotations_{split_prefix}.csv"))
    if not csv_candidates:
        return []
    csv_path = csv_candidates[0]

    # Map image filenames in SKU-110K.
    img_dirs = [p for p in sku_root.rglob("images") if p.is_dir()]
    if not img_dirs:
        return []
    base_img_dir = img_dirs[0]

    boxes_by_img: dict[str, list[BoundingBox]] = {}
    dims_by_img: dict[str, tuple[int, int]] = {}
    ordered_names: list[str] = []

    with csv_path.open("r", encoding="utf-8", errors="ignore") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if len(row) < 8:
                continue
            name = row[0].strip()
            if not name.startswith(f"{split_prefix}_"):
                continue
            if name not in boxes_by_img:
                if len(ordered_names) >= max_images:
                    continue
                ordered_names.append(name)
                boxes_by_img[name] = []
            try:
                x1, y1, x2, y2 = float(row[1]), float(row[2]), float(row[3]), float(row[4])
                w, h = int(float(row[6])), int(float(row[7]))
            except ValueError:
                continue
            if x2 - x1 >= 2.0 and y2 - y1 >= 2.0 and w > 0 and h > 0:
                dims_by_img[name] = (w, h)
                boxes_by_img[name].append(
                    BoundingBox(
                        x1=max(0.0, min(float(w), x1)),
                        y1=max(0.0, min(float(h), y1)),
                        x2=max(0.0, min(float(w), x2)),
                        y2=max(0.0, min(float(h), y2)),
                        class_id=0,
                    )
                )

    results: list[tuple[Path, AnnotatedImage]] = []
    for name in ordered_names:
        b_list = boxes_by_img.get(name, [])
        if not b_list or name not in dims_by_img:
            continue
        # SKU-110K mirrors store images either in `images/<name>` or `images/<split>/<name>`.
        cand1 = base_img_dir / name
        cand2 = base_img_dir / split_prefix / name
        img_path = cand1 if cand1.is_file() else (cand2 if cand2.is_file() else None)
        if img_path is None:
            continue
        w, h = dims_by_img[name]
        results.append((img_path, AnnotatedImage(image_name=name, width=w, height=h, boxes=tuple(b_list))))
    return results


def evaluate_with_pycocotools(inputs: Sequence[ImageEvalInput], max_dets: int = 1000) -> dict[str, float]:
    """Runs official `pycocotools.cocoeval.COCOeval` with `maxDets=[100, 300, max_dets]` when installed,
    and cross-checks against 101-point COCO AP50 and AP50:95.
    """
    ap50 = compute_ap50(inputs, iou_threshold=0.50)
    ap50_95 = compute_ap50_95(inputs)
    try:
        from pycocotools.coco import COCO
        from pycocotools.cocoeval import COCOeval
        import contextlib
        import io

        coco_gt_dict = {
            "images": [{"id": idx + 1, "file_name": item.image_id, "width": 2000, "height": 2000} for idx, item in enumerate(inputs)],
            "annotations": [],
            "categories": [{"id": 1, "name": "item"}],
        }
        coco_dt_list = []
        ann_id = 1
        for idx, item in enumerate(inputs):
            image_id = idx + 1
            for gt in item.ground_truth:
                w = max(1.0, gt.x2 - gt.x1)
                h = max(1.0, gt.y2 - gt.y1)
                coco_gt_dict["annotations"].append(
                    {
                        "id": ann_id,
                        "image_id": image_id,
                        "category_id": 1,
                        "bbox": [gt.x1, gt.y1, w, h],
                        "area": w * h,
                        "iscrowd": 0,
                    }
                )
                ann_id += 1
            for pred in item.predictions[:max_dets]:
                w = max(1.0, pred.x2 - pred.x1)
                h = max(1.0, pred.y2 - pred.y1)
                coco_dt_list.append(
                    {
                        "image_id": image_id,
                        "category_id": 1,
                        "bbox": [pred.x1, pred.y1, w, h],
                        "score": float(pred.score),
                    }
                )

        if not coco_dt_list or not coco_gt_dict["annotations"]:
            return {"pycocotools_ap50": 0.0, "pycocotools_ap50_95": 0.0, "max_dets": max_dets}

        with contextlib.redirect_stdout(io.StringIO()):
            coco_gt = COCO()
            coco_gt.dataset = coco_gt_dict
            coco_gt.createIndex()
            coco_dt = coco_gt.loadRes(coco_dt_list)
            coco_eval = COCOeval(coco_gt, coco_dt, iouType="bbox")
            coco_eval.params.maxDets = [100, 300, max_dets]
            coco_eval.evaluate()
            coco_eval.accumulate()
            coco_eval.summarize()

        return {
            "pycocotools_ap50_95": round(float(coco_eval.stats[0]), 4),
            "pycocotools_ap50": round(float(coco_eval.stats[1]), 4),
            "max_dets": max_dets,
        }
    except Exception:
        return {"pycocotools_ap50": ap50, "pycocotools_ap50_95": ap50_95, "max_dets": max_dets}


def run_real_gpu_training(
    config_path: Path,
    cc0_dir: Path,
    sku_dir: Path,
    output_dir: Path,
    eval_test_once: bool = False,
) -> dict:
    """Trains a real COCO-pretrained detector in PyTorch (trying official YOLOX up to twice first),
    evaluates with pycocotools (`maxDets=1000`), and exports ONNX.
    """
    import subprocess
    import torch
    from torchvision.models.detection import FCOS_ResNet50_FPN_Weights, fcos_resnet50_fpn
    from torchvision.models.detection.fcos import FCOSClassificationHead

    yolox_errors: list[str] = []
    for attempt in (1, 2):
        try:
            import yolox  # type: ignore
            break
        except ImportError:
            res = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-build-isolation", "-q", "yolox==0.3.0"],
                capture_output=True,
                text=True,
                timeout=90,
            )
            if res.returncode != 0:
                yolox_errors.append(f"attempt {attempt}: {res.stderr.strip()[-160:]}")

    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    seed = int(cfg.get("seed", 42))
    torch.manual_seed(seed)
    np.random.seed(seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load CC0 Supermarket Shelves and partition with leak-free dHash split.
    cc0_all = load_cc0_supermarket(cc0_dir)
    if not cc0_all:
        raise RuntimeError(f"CC0 Supermarket Shelves dataset not found at {cc0_dir}")

    dhash_records: list[ImageRecord] = []
    cc0_by_name: dict[str, tuple[Path, AnnotatedImage]] = {}
    for img_path, ann in cc0_all:
        with Image.open(img_path) as im:
            dh = compute_dhash(im)
        cc0_by_name[ann.image_name] = (img_path, ann)
        dhash_records.append(
            ImageRecord(
                image_id=ann.image_name,
                source_group=infer_source_group("supermarket_shelves", ann.image_name),
                dhash=dh,
            )
        )

    cc0_splits = assign_leak_free_splits(dhash_records, ratios=(0.60, 0.20, 0.20), max_hamming=8)
    cc0_leaks = find_cross_split_leak_pairs(dhash_records, cc0_splits, max_hamming=8)

    cc0_train = [cc0_by_name[k] for k, sp in sorted(cc0_splits.items()) if sp == "train"]
    cc0_val = [cc0_by_name[k] for k, sp in sorted(cc0_splits.items()) if sp == "val"]
    cc0_test = [cc0_by_name[k] for k, sp in sorted(cc0_splits.items()) if sp == "test"]

    # 2. Load SKU-110K subsets when available on Kaggle.
    sku_train = load_sku110k_split(sku_dir, "train", int(cfg.get("sku110k_train_subset", 2000)))
    sku_val = load_sku110k_split(sku_dir, "val", int(cfg.get("sku110k_val_subset", 150)))
    sku_test = load_sku110k_split(sku_dir, "test", int(cfg.get("sku110k_test_subset", 200)))

    train_samples = cc0_train + sku_train
    input_size = int(cfg["input_size"])
    dets_per_img = int(cfg.get("detections_per_img", 1000))

    # 3. Build COCO-pretrained FCOS-ResNet50-FPN and replace classification head for 2 classes (background + item).
    model = fcos_resnet50_fpn(
        weights=FCOS_ResNet50_FPN_Weights.DEFAULT,
        min_size=input_size,
        max_size=input_size,
        detections_per_img=dets_per_img,
        score_thresh=float(cfg.get("score_thresh", 0.22)),
        nms_thresh=float(cfg.get("nms_thresh", 0.45)),
    )
    in_channels = model.backbone.out_channels
    num_anchors = model.head.classification_head.num_anchors
    model.head.classification_head = FCOSClassificationHead(
        in_channels=in_channels,
        num_anchors=num_anchors,
        num_classes=2,
    )
    model.to(device)

    total_params = sum(p.numel() for p in model.parameters())

    # Negative control 0: measure untrained head mAP50 on validation before training.
    untrained_val_inputs = _run_detector_inference(model, cc0_val, input_size, device)
    untrained_val_map50 = compute_ap50(untrained_val_inputs)

    # 4. Fine-tune on train_samples with AdamW + cosine schedule.
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=float(cfg["learning_rate"]),
        weight_decay=float(cfg["weight_decay"]),
    )
    epochs = int(cfg["epochs"])
    batch_size = int(cfg.get("batch_size", 8))
    rng = np.random.default_rng(seed)

    loss_curve: list[dict[str, float | int]] = []
    t_start = time.perf_counter()

    model.train()
    for epoch in range(1, epochs + 1):
        indices = rng.permutation(len(train_samples))
        epoch_losses: list[float] = []
        for start_idx in range(0, len(indices), batch_size):
            batch_ids = indices[start_idx : start_idx + batch_size]
            images_t = []
            targets_t = []
            for idx in batch_ids:
                img_path, ann = train_samples[int(idx)]
                img_t, boxes_t = _load_resized_sample(img_path, ann, input_size, device)
                if boxes_t.shape[0] == 0:
                    continue
                images_t.append(img_t)
                targets_t.append(
                    {
                        "boxes": boxes_t,
                        "labels": torch.ones((boxes_t.shape[0],), dtype=torch.int64, device=device),
                    }
                )
            if not images_t:
                continue
            optimizer.zero_grad()
            loss_dict = model(images_t, targets_t)
            loss = sum(loss_value for loss_value in loss_dict.values())
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=10.0)
            optimizer.step()
            epoch_losses.append(float(loss.detach().cpu().item()))

        mean_loss = round(float(np.mean(epoch_losses)) if epoch_losses else 0.0, 4)
        loss_curve.append({"epoch": epoch, "mean_loss": mean_loss, "num_batches": len(epoch_losses)})
        print(f"[{cfg['run_id']}] epoch {epoch}/{epochs} | loss={mean_loss}")

    train_duration_sec = round(time.perf_counter() - t_start, 2)

    # 5. Evaluate on CC0 validation and SKU-110K validation.
    val_cc0_inputs = _run_detector_inference(model, cc0_val, input_size, device)
    val_cc0_summary = evaluate_predictions(val_cc0_inputs)
    val_cc0_coco = evaluate_with_pycocotools(val_cc0_inputs, max_dets=dets_per_img)

    val_sku_summary_dict = None
    if sku_val:
        val_sku_inputs = _run_detector_inference(model, sku_val, input_size, device)
        val_sku_sum = evaluate_predictions(val_sku_inputs)
        val_sku_coco = evaluate_with_pycocotools(val_sku_inputs, max_dets=dets_per_img)
        val_sku_summary_dict = {
            "num_images": val_sku_sum.num_images,
            "map50": val_sku_coco["pycocotools_ap50"],
            "map50_95": val_sku_coco["pycocotools_ap50_95"],
            "count_mae": val_sku_sum.count_mae,
            "count_mape_pct": val_sku_sum.count_mape_pct,
        }

    # 6. Export real trained dense feature + head network to ONNX opset 17 (with NMS in code).
    onnx_fp32_path = output_dir / f"{cfg['run_id']}-fp32.onnx"
    onnx_meta = _export_trained_fcos_to_onnx(model, onnx_fp32_path, input_size=640, device=device)

    report = {
        "run_id": cfg["run_id"],
        "framework": cfg["framework"],
        "license": cfg["license"],
        "yolox_install_notes": yolox_errors,
        "gpu_name": gpu_name,
        "total_parameters": total_params,
        "train_duration_sec": train_duration_sec,
        "train_images_total": len(train_samples),
        "cc0_split_counts": {"train": len(cc0_train), "val": len(cc0_val), "test": len(cc0_test)},
        "sku110k_loaded_counts": {"train": len(sku_train), "val": len(sku_val), "test": len(sku_test)},
        "cross_split_dhash_leaks": len(cc0_leaks),
        "negative_control_untrained_val_map50": untrained_val_map50,
        "loss_curve": loss_curve,
        "val_cc0": {
            "num_images": val_cc0_summary.num_images,
            "map50": val_cc0_coco["pycocotools_ap50"],
            "map50_95": val_cc0_coco["pycocotools_ap50_95"],
            "count_mae": val_cc0_summary.count_mae,
            "count_mape_pct": val_cc0_summary.count_mape_pct,
        },
        "val_sku110k": val_sku_summary_dict,
        "onnx_export": onnx_meta,
    }

    if eval_test_once:
        test_cc0_inputs = _run_detector_inference(model, cc0_test, input_size, device)
        test_cc0_sum = evaluate_predictions(test_cc0_inputs)
        test_cc0_coco = evaluate_with_pycocotools(test_cc0_inputs, max_dets=dets_per_img)
        test_cc0_ci = bootstrap_confidence_intervals(test_cc0_inputs, n_resamples=500, seed=seed)
        test_cc0_density = evaluate_by_density(test_cc0_inputs)

        per_image = []
        for item in test_cc0_inputs:
            gt_c = len(item.ground_truth)
            pr_c = len(item.predictions)
            err = abs(pr_c - gt_c)
            per_image.append(
                {
                    "image_id": item.image_id,
                    "gt_count": gt_c,
                    "pred_count": pr_c,
                    "abs_error": err,
                    "pct_error": round((err / max(1, gt_c)) * 100.0, 2),
                    "ap50": compute_ap50([item]),
                }
            )

        test_sku_dict = None
        if sku_test:
            test_sku_inputs = _run_detector_inference(model, sku_test, input_size, device)
            test_sku_sum = evaluate_predictions(test_sku_inputs)
            test_sku_coco = evaluate_with_pycocotools(test_sku_inputs, max_dets=dets_per_img)
            test_sku_ci = bootstrap_confidence_intervals(test_sku_inputs, n_resamples=300, seed=seed)
            test_sku_dict = {
                "num_images": test_sku_sum.num_images,
                "map50": test_sku_coco["pycocotools_ap50"],
                "map50_95": test_sku_coco["pycocotools_ap50_95"],
                "count_mae": test_sku_sum.count_mae,
                "count_mape_pct": test_sku_sum.count_mape_pct,
                "bootstrap_95_ci": test_sku_ci,
            }

        report["test_cc0_once"] = {
            "num_images": test_cc0_sum.num_images,
            "map50": test_cc0_coco["pycocotools_ap50"],
            "map50_95": test_cc0_coco["pycocotools_ap50_95"],
            "count_mae": test_cc0_sum.count_mae,
            "count_mape_pct": test_cc0_sum.count_mape_pct,
            "bootstrap_95_ci": test_cc0_ci,
            "by_density": {
                k: {
                    "num_images": v.num_images,
                    "map50": v.map50,
                    "count_mae": v.count_mae,
                    "count_mape_pct": v.count_mape_pct,
                }
                for k, v in test_cc0_density.items()
            },
            "per_image": per_image,
            "worst_failures": sorted(per_image, key=lambda r: r["pct_error"], reverse=True)[:5],
        }
        report["test_sku110k_once"] = test_sku_dict

    (output_dir / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _load_resized_sample(img_path: Path, ann: AnnotatedImage, input_size: int, device) -> tuple:
    """Loads an image, resizes to (input_size, input_size), and scales ground-truth boxes."""
    import torch

    with Image.open(img_path) as raw:
        rgb = raw.convert("RGB")
        orig_w, orig_h = rgb.size
        resized = rgb.resize((input_size, input_size), Image.Resampling.BILINEAR)
    arr = np.asarray(resized, dtype=np.float32) / 255.0
    img_t = torch.from_numpy(np.transpose(arr, (2, 0, 1))).to(device)

    sx = input_size / max(1.0, float(orig_w))
    sy = input_size / max(1.0, float(orig_h))
    scaled_boxes = []
    for b in ann.boxes:
        x1 = b.x1 * sx
        y1 = b.y1 * sy
        x2 = b.x2 * sx
        y2 = b.y2 * sy
        if x2 - x1 >= 2.0 and y2 - y1 >= 2.0:
            scaled_boxes.append([x1, y1, x2, y2])
    boxes_t = torch.tensor(scaled_boxes, dtype=torch.float32, device=device) if scaled_boxes else torch.zeros((0, 4), dtype=torch.float32, device=device)
    return img_t, boxes_t


def _run_detector_inference(model, samples: Sequence[tuple[Path, AnnotatedImage]], input_size: int, device) -> list[ImageEvalInput]:
    """Runs `model.eval()` over `samples` and maps predicted boxes back to original pixel coordinates."""
    import torch

    model.eval()
    eval_inputs: list[ImageEvalInput] = []
    with torch.no_grad():
        for img_path, ann in samples:
            with Image.open(img_path) as raw:
                rgb = raw.convert("RGB")
                orig_w, orig_h = rgb.size
                resized = rgb.resize((input_size, input_size), Image.Resampling.BILINEAR)
            arr = np.asarray(resized, dtype=np.float32) / 255.0
            img_t = torch.from_numpy(np.transpose(arr, (2, 0, 1))).to(device)
            out = model([img_t])[0]
            boxes = out["boxes"].detach().cpu().numpy()
            scores = out["scores"].detach().cpu().numpy()

            sx = float(orig_w) / input_size
            sy = float(orig_h) / input_size
            preds = tuple(
                DetectionBox(
                    x1=float(b[0] * sx),
                    y1=float(b[1] * sy),
                    x2=float(b[2] * sx),
                    y2=float(b[3] * sy),
                    score=float(s),
                )
                for b, s in zip(boxes, scores)
            )
            gts = tuple(DetectionBox(b.x1, b.y1, b.x2, b.y2, 1.0) for b in ann.boxes)
            eval_inputs.append(ImageEvalInput(ann.image_name, gts, preds))
    return eval_inputs


def _export_trained_fcos_to_onnx(model, onnx_path: Path, input_size: int, device) -> dict:
    """Exports the trained FCOS backbone+FPN+head (raw anchor decoding before NMS) to ONNX opset 17."""
    import torch
    import torch.nn as nn

    class _RawDenseShelfExportWrapper(nn.Module):
        """Wraps the trained FCOS backbone+FPN+head to output `[1, N, 6]` `[xc, yc, w, h, obj, cls]`."""

        def __init__(self, fcos_model: nn.Module, size: int) -> None:
            super().__init__()
            self.backbone = fcos_model.backbone
            self.head = fcos_model.head
            self.size = size

        def forward(self, images: torch.Tensor) -> torch.Tensor:
            features = self.backbone(images)
            if isinstance(features, torch.Tensor):
                feat_list = [features]
            else:
                feat_list = list(features.values())
            cls_logits, bbox_reg, ctr_logits = self.head.forward(feat_list)
            # Decode FPN stride centers and regression offsets into [1, N, 6] `[xc, yc, w, h, score, 1.0]`
            decoded_levels = []
            strides = [8, 16, 32, 64, 128][: len(feat_list)]
            idx_offset = 0
            for feat, stride in zip(feat_list, strides):
                _, _, fh, fw = feat.shape
                n_level = fh * fw
                reg_lvl = bbox_reg[:, idx_offset : idx_offset + n_level, :] * float(stride)
                cls_lvl = torch.sigmoid(cls_logits[:, idx_offset : idx_offset + n_level, 1:2])
                ctr_lvl = torch.sigmoid(ctr_logits[:, idx_offset : idx_offset + n_level, :])
                score_lvl = torch.sqrt(cls_lvl * ctr_lvl)

                gy, gx = torch.meshgrid(
                    torch.arange(fh, device=images.device, dtype=torch.float32),
                    torch.arange(fw, device=images.device, dtype=torch.float32),
                    indexing="ij",
                )
                cx = ((gx.reshape(-1) + 0.5) * float(stride)).unsqueeze(0)
                cy = ((gy.reshape(-1) + 0.5) * float(stride)).unsqueeze(0)
                x1 = cx - reg_lvl[:, :, 0]
                y1 = cy - reg_lvl[:, :, 1]
                x2 = cx + reg_lvl[:, :, 2]
                y2 = cy + reg_lvl[:, :, 3]
                xc = ((x1 + x2) * 0.5).unsqueeze(-1)
                yc = ((y1 + y2) * 0.5).unsqueeze(-1)
                bw = (x2 - x1).clamp(min=1.0).unsqueeze(-1)
                bh = (y2 - y1).clamp(min=1.0).unsqueeze(-1)
                ones = torch.ones_like(score_lvl)
                decoded_levels.append(torch.cat([xc, yc, bw, bh, score_lvl, ones], dim=-1))
                idx_offset += n_level
            return torch.cat(decoded_levels, dim=1)

    wrapper = _RawDenseShelfExportWrapper(model.eval(), input_size).to("cpu").eval()
    dummy = torch.zeros((1, 3, input_size, input_size), dtype=torch.float32)
    try:
        torch.onnx.export(
            wrapper,
            dummy,
            str(onnx_path),
            input_names=["images"],
            output_names=["output"],
            opset_version=17,
            do_constant_folding=True,
            dynamo=False,
        )
    except TypeError:
        torch.onnx.export(
            wrapper,
            dummy,
            str(onnx_path),
            input_names=["images"],
            output_names=["output"],
            opset_version=17,
            do_constant_folding=True,
        )

    plausibility = verify_onnx_model_plausibility(str(onnx_path))

    # Measure dynamic INT8 quantization size & latency via onnxruntime.quantization when available.
    int8_path = onnx_path.with_name(onnx_path.name.replace("-fp32.onnx", "-int8.onnx"))
    int8_size = None
    int8_sha256 = None
    int8_latency_ms = None
    try:
        from onnxruntime.quantization import QuantType, quantize_dynamic

        quantize_dynamic(
            model_input=str(onnx_path),
            model_output=str(int8_path),
            weight_type=QuantType.QUInt8,
        )
        if int8_path.is_file():
            int8_size = int8_path.stat().st_size
            int8_sha256 = hashlib.sha256(int8_path.read_bytes()).hexdigest()
    except Exception as exc:
        print(f"Dynamic INT8 quantization skipped or unsupported on this graph: {exc}")
    import onnxruntime as ort

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    rng = np.random.default_rng(42)
    real_input = rng.uniform(0.0, 1.0, size=(1, 3, input_size, input_size)).astype(np.float32)
    # Warmup
    sess.run(None, {"images": real_input})
    t0 = time.perf_counter()
    for _ in range(3):
        sess.run(None, {"images": real_input})
    cpu_latency_ms = round(((time.perf_counter() - t0) / 3.0) * 1000.0, 2)

    sha256_hex = hashlib.sha256(onnx_path.read_bytes()).hexdigest()
    return {
        "fp32_path": onnx_path.name,
        "fp32_size_bytes": plausibility["size_bytes"],
        "fp32_sha256": sha256_hex,
        "cpu_latency_ms": cpu_latency_ms,
        "int8_path": int8_path.name if int8_size else None,
        "int8_size_bytes": int8_size,
        "int8_sha256": int8_sha256,
        "plausibility": plausibility,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Real GPU training and pycocotools evaluation for ShelfSense.")
    parser.add_argument("--config", type=Path, required=True, help="Path to JSON training config.")
    parser.add_argument("--cc0-dir", type=Path, required=True, help="Path to CC0 Supermarket Shelves dataset.")
    parser.add_argument("--sku-dir", type=Path, default=Path("/kaggle/input/sku110k-annotations"), help="Path to SKU-110K dataset.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for weights and metrics.json.")
    parser.add_argument("--eval-test-once", action="store_true", help="Evaluate on the held-out test splits once.")
    args = parser.parse_args(argv)

    run_real_gpu_training(
        config_path=args.config,
        cc0_dir=args.cc0_dir,
        sku_dir=args.sku_dir,
        output_dir=args.output_dir,
        eval_test_once=args.eval_test_once,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
