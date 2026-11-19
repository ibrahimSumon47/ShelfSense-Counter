"""ONNX-path inference and evaluation (numpy + onnxruntime only, no torch).

The exported detector returns raw dense candidates `[1, N, 6] = [xc, yc, w, h, score, 1]` in
input-pixel coordinates; thresholding, NMS and the cap on detections are done here in code.
The same logic is what the Python CLI and the browser must reproduce.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np

from shelfsense_training.data import Sample, load_square_uint8
from shelfsense_training.metrics import DetectionBox, ImageEvalInput, evaluate_predictions

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 3, 1, 1)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 3, 1, 1)
STRIDES = (8, 16, 32, 64, 128)


def level_sizes(input_size: int) -> list[tuple[int, int]]:
    """(grid cells, stride) per FPN level for an input size that is a multiple of 128."""
    if input_size % 128:
        raise ValueError("input_size must be a multiple of 128 so FCOS anchor strides are exact")
    return [(input_size // s, s) for s in STRIDES]


def legacy_center_fix(raw: np.ndarray, input_size: int) -> np.ndarray:
    """Shifts anchor centres by half a stride per FPN level.

    torchvision places FCOS anchor centres at g*stride + stride/2; an export that placed them
    at g*stride alone is off by half a cell and can be corrected here. Measured on the CC0
    validation split: applying this to the stored exports lowers AP, so they already match.
    """
    fixed = raw.copy()
    offset = 0
    for cells, stride in level_sizes(input_size):
        n = cells * cells
        fixed[:, offset : offset + n, 0] -= 0.5 * stride
        fixed[:, offset : offset + n, 1] -= 0.5 * stride
        offset += n
    return fixed


def nms_numpy(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float) -> np.ndarray:
    """Greedy NMS; returns kept indices sorted by descending score."""
    order = np.argsort(-scores)
    keep: list[int] = []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    while order.size:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        iw = np.maximum(0.0, np.minimum(x2[i], x2[rest]) - np.maximum(x1[i], x1[rest]))
        ih = np.maximum(0.0, np.minimum(y2[i], y2[rest]) - np.maximum(y1[i], y1[rest]))
        inter = iw * ih
        iou = inter / np.maximum(areas[i] + areas[rest] - inter, 1e-9)
        order = rest[iou <= iou_thresh]
    return np.asarray(keep, dtype=np.int64)


def decode_raw(
    raw: np.ndarray,
    input_size: int,
    orig_w: int,
    orig_h: int,
    score_thresh: float,
    nms_thresh: float,
    max_dets: int = 1000,
    topk: int = 3000,
) -> tuple[np.ndarray, np.ndarray]:
    """Turns raw `[N, 6]` candidates into (boxes xyxy in original pixels, scores)."""
    cand = raw.reshape(-1, raw.shape[-1])
    keep = cand[:, 4] >= score_thresh
    cand = cand[keep]
    if cand.shape[0] == 0:
        return np.zeros((0, 4), np.float32), np.zeros((0,), np.float32)
    if cand.shape[0] > topk:
        cand = cand[np.argsort(-cand[:, 4])[:topk]]
    xc, yc, w, h, s = cand[:, 0], cand[:, 1], cand[:, 2], cand[:, 3], cand[:, 4]
    boxes = np.stack([xc - w / 2, yc - h / 2, xc + w / 2, yc + h / 2], axis=1)
    boxes = np.clip(boxes, 0.0, float(input_size))
    valid = ((boxes[:, 2] - boxes[:, 0]) >= 1.0) & ((boxes[:, 3] - boxes[:, 1]) >= 1.0)
    boxes, s = boxes[valid], s[valid]
    kept = nms_numpy(boxes, s, nms_thresh)[:max_dets]
    boxes, s = boxes[kept], s[kept]
    boxes = boxes * np.array([orig_w / input_size, orig_h / input_size] * 2, dtype=np.float32)
    return boxes.astype(np.float32), s.astype(np.float32)


def run_raw_candidates(
    session,
    samples: Sequence[Sample],
    input_size: int,
    normalise: bool = True,
    center_fix: str = "none",
) -> list[tuple[np.ndarray, int, int]]:
    """Runs the ONNX session once per image and keeps the raw candidates, so score and NMS
    thresholds can be swept without re-running the network.

    `normalise` applies the ImageNet mean/std in numpy. The exported wrapper calls the FCOS
    backbone directly and therefore skips torchvision's transform, which is where the model
    normalises its input during training; the first exports assumed the caller did it.
    `center_fix="legacy"` shifts anchor centres back for graphs built with the wrong offset.
    """
    name = session.get_inputs()[0].name
    cached = []
    for path, _ann in samples:
        arr, ow, oh = load_square_uint8(path, input_size)
        x = (arr.transpose(2, 0, 1)[None].astype(np.float32)) / 255.0
        if normalise:
            x = (x - IMAGENET_MEAN) / IMAGENET_STD
        raw = session.run(None, {name: x})[0][0]
        if center_fix == "legacy":
            raw = legacy_center_fix(raw[None], input_size)[0]
        cached.append((raw, ow, oh))
    return cached


def to_eval_inputs(samples: Sequence[Sample], cached, input_size: int, score_thresh: float, nms_thresh: float, max_dets: int) -> list[ImageEvalInput]:
    """Applies thresholds to cached raw candidates and pairs them with ground truth."""
    out = []
    for (_p, ann), (raw, ow, oh) in zip(samples, cached):
        boxes, scores = decode_raw(raw, input_size, ow, oh, score_thresh, nms_thresh, max_dets)
        preds = tuple(DetectionBox(float(b[0]), float(b[1]), float(b[2]), float(b[3]), float(s)) for b, s in zip(boxes, scores))
        gts = tuple(DetectionBox(b.x1, b.y1, b.x2, b.y2, 1.0) for b in ann.boxes)
        out.append(ImageEvalInput(ann.image_name, gts, preds))
    return out


def make_session(onnx_path: Path):
    """CPU onnxruntime session for an exported model."""
    import onnxruntime as ort

    return ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])


def sweep_thresholds(
    samples: Sequence[Sample],
    cached,
    input_size: int,
    score_grid: Sequence[float],
    nms_grid: Sequence[float],
    max_dets: int = 1000,
) -> list[dict]:
    """Evaluates every (score, NMS) pair on cached candidates and returns one row per pair.

    Thresholds are chosen on validation data only; the row with the highest mAP50 wins and is
    written into metrics.json, so the shipped artefacts and the reported numbers use the same
    settings the browser will use.
    """
    from shelfsense_training.coco_eval import coco_ap

    rows: list[dict] = []
    for score_thresh in score_grid:
        for nms_thresh in nms_grid:
            eval_inputs = to_eval_inputs(samples, cached, input_size, score_thresh, nms_thresh, max_dets)
            summary = evaluate_predictions(eval_inputs)
            coco = coco_ap(eval_inputs, max_dets=max_dets)
            rows.append(
                {
                    "score_thresh": round(float(score_thresh), 3),
                    "nms_thresh": round(float(nms_thresh), 3),
                    "max_dets": max_dets,
                    "map50": coco["map50"],
                    "map50_95": coco["map"],
                    "count_mae": summary.count_mae,
                    "count_mape_pct": summary.count_mape_pct,
                    "pred_count_total": sum(len(i.predictions) for i in eval_inputs),
                }
            )
    return rows


def best_threshold_row(rows: list[dict]) -> dict:
    """Highest mAP50 wins; ties are broken by the lower count MAE."""
    return sorted(rows, key=lambda r: (-r["map50"], r["count_mae"]))[0]
