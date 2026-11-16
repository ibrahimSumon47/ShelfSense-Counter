"""Evaluation metrics for dense retail shelf detection and inventory counting.

Computes:
- Bounding-box IoU and single-class AP@0.50 (mAP50) via 101-point COCO interpolation.
- Inventory count Mean Absolute Error (MAE) and Mean Absolute Percentage Error (MAPE).
- Metrics stratified by shelf density (sparse: <50 items, medium: 50-150, dense: >150).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class DetectionBox:
    """A predicted or ground-truth bounding box in pixel coordinates."""

    x1: float
    y1: float
    x2: float
    y2: float
    score: float = 1.0


@dataclass(frozen=True)
class ImageEvalInput:
    """Ground-truth and predicted boxes for a single shelf image."""

    image_id: str
    ground_truth: tuple[DetectionBox, ...]
    predictions: tuple[DetectionBox, ...]


@dataclass(frozen=True)
class EvalSummary:
    """Aggregated detection and counting accuracy metrics."""

    num_images: int
    map50: float
    count_mae: float
    count_mape_pct: float
    exact_within_tolerance_pct: float


def box_iou(a: DetectionBox, b: DetectionBox) -> float:
    """Computes Intersection-over-Union (IoU) between two axis-aligned boxes."""
    ix1 = max(a.x1, b.x1)
    iy1 = max(a.y1, b.y1)
    ix2 = min(a.x2, b.x2)
    iy2 = min(a.y2, b.y2)
    inter_w = max(0.0, ix2 - ix1)
    inter_h = max(0.0, iy2 - iy1)
    inter = inter_w * inter_h
    if inter <= 0.0:
        return 0.0
    area_a = max(0.0, a.x2 - a.x1) * max(0.0, a.y2 - a.y1)
    area_b = max(0.0, b.x2 - b.x1) * max(0.0, b.y2 - b.y1)
    union = area_a + area_b - inter
    return inter / union if union > 0.0 else 0.0


def nms(boxes: Sequence[DetectionBox], iou_threshold: float = 0.45) -> list[DetectionBox]:
    """Applies standard greedy Non-Maximum Suppression sorted by descending score."""
    ordered = sorted(boxes, key=lambda b: b.score, reverse=True)
    kept: list[DetectionBox] = []
    for candidate in ordered:
        if all(box_iou(candidate, existing) <= iou_threshold for existing in kept):
            kept.append(candidate)
    return kept


def compute_ap50(inputs: Sequence[ImageEvalInput], iou_threshold: float = 0.50) -> float:
    """Computes single-class AP@0.50 using 101-point recall interpolation."""
    total_gt = sum(len(item.ground_truth) for item in inputs)
    if total_gt == 0:
        return 0.0

    # Flatten all predictions across images, sorted by score descending.
    flat_preds: list[tuple[float, str, DetectionBox]] = []
    gt_by_image: dict[str, tuple[DetectionBox, ...]] = {}
    matched_gt: dict[str, set[int]] = {}

    for item in inputs:
        gt_by_image[item.image_id] = item.ground_truth
        matched_gt[item.image_id] = set()
        for pred in item.predictions:
            flat_preds.append((pred.score, item.image_id, pred))

    flat_preds.sort(key=lambda t: t[0], reverse=True)

    tp_Flags: list[int] = []
    fp_Flags: list[int] = []

    for _, img_id, pred in flat_preds:
        gts = gt_by_image[img_id]
        used = matched_gt[img_id]
        best_iou = 0.0
        best_idx = -1
        for idx, gt in enumerate(gts):
            if idx in used:
                continue
            iou = box_iou(pred, gt)
            if iou > best_iou:
                best_iou = iou
                best_idx = idx
        if best_iou >= iou_threshold and best_idx >= 0:
            used.add(best_idx)
            tp_Flags.append(1)
            fp_Flags.append(0)
        else:
            tp_Flags.append(0)
            fp_Flags.append(1)

    precisions: list[float] = []
    recalls: list[float] = []
    cum_tp = 0
    cum_fp = 0
    for tp, fp in zip(tp_Flags, fp_Flags):
        cum_tp += tp
        cum_fp += fp
        precisions.append(cum_tp / (cum_tp + cum_fp))
        recalls.append(cum_tp / total_gt)

    # 101-point COCO interpolation from recall 0.00 to 1.00.
    ap_sum = 0.0
    for step in range(101):
        r_thresh = step / 100.0
        max_p = max((p for p, r in zip(precisions, recalls) if r >= r_thresh), default=0.0)
        ap_sum += max_p
    return round(ap_sum / 101.0, 4)


def evaluate_predictions(
    inputs: Sequence[ImageEvalInput],
    count_tolerance_ratio: float = 0.10,
) -> EvalSummary:
    """Computes mAP50, count MAE, count MAPE (%), and within-tolerance pass rate."""
    if not inputs:
        return EvalSummary(0, 0.0, 0.0, 0.0, 0.0)

    map50 = compute_ap50(inputs, iou_threshold=0.50)
    abs_errors: list[float] = []
    pct_errors: list[float] = []
    within_tol = 0

    for item in inputs:
        gt_count = len(item.ground_truth)
        pred_count = len(item.predictions)
        err = abs(pred_count - gt_count)
        abs_errors.append(float(err))
        denom = max(1, gt_count)
        pct_err = (err / denom) * 100.0
        pct_errors.append(pct_err)
        allowed = max(1, round(gt_count * count_tolerance_ratio))
        if err <= allowed:
            within_tol += 1

    n = len(inputs)
    return EvalSummary(
        num_images=n,
        map50=map50,
        count_mae=round(sum(abs_errors) / n, 2),
        count_mape_pct=round(sum(pct_errors) / n, 2),
        exact_within_tolerance_pct=round((within_tol / n) * 100.0, 2),
    )


def density_bucket(gt_count: int) -> str:
    """Assigns a shelf image to a density bucket based on ground-truth item count."""
    if gt_count < 50:
        return "sparse (<50)"
    if gt_count <= 150:
        return "medium (50-150)"
    return "dense (>150)"


def evaluate_by_density(inputs: Sequence[ImageEvalInput]) -> dict[str, EvalSummary]:
    """Breaks down evaluation metrics across sparse, medium, and dense shelves."""
    buckets: dict[str, list[ImageEvalInput]] = {
        "sparse (<50)": [],
        "medium (50-150)": [],
        "dense (>150)": [],
    }
    for item in inputs:
        buckets[density_bucket(len(item.ground_truth))].append(item)
    return {name: evaluate_predictions(group) for name, group in buckets.items()}
