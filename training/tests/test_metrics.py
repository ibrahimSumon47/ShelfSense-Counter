"""Unit tests for mAP50, NMS, count MAE/MAPE, and shelf density stratification."""
from shelfsense_training.metrics import (
    DetectionBox,
    ImageEvalInput,
    box_iou,
    compute_ap50,
    density_bucket,
    evaluate_by_density,
    evaluate_predictions,
    nms,
)


def test_box_iou_and_nms() -> None:
    """NMS suppresses overlapping lower-scoring boxes and retains distinct products."""
    b1 = DetectionBox(10, 10, 50, 50, score=0.95)
    b1_dup = DetectionBox(12, 12, 52, 52, score=0.70)
    b2 = DetectionBox(100, 10, 140, 50, score=0.88)

    assert box_iou(b1, b1_dup) > 0.65
    assert box_iou(b1, b2) == 0.0
    kept = nms([b1_dup, b2, b1], iou_threshold=0.45)
    assert kept == [b1, b2]


def test_ap50_and_count_metrics() -> None:
    """Perfect predictions yield mAP50=1.0 and MAE=0; slight count offset gives exact MAE/MAPE."""
    gt = (
        DetectionBox(0, 0, 20, 20),
        DetectionBox(30, 0, 50, 20),
        DetectionBox(60, 0, 80, 20),
        DetectionBox(90, 0, 110, 20),
    )
    preds_exact = (
        DetectionBox(1, 1, 20, 20, score=0.9),
        DetectionBox(30, 0, 50, 20, score=0.8),
        DetectionBox(60, 0, 80, 20, score=0.7),
        DetectionBox(90, 0, 110, 20, score=0.6),
    )
    item1 = ImageEvalInput("img1", ground_truth=gt, predictions=preds_exact)
    assert compute_ap50([item1]) == 1.0

    # Second image misses 1 of 4 items (count error = 1, MAPE = 25%).
    item2 = ImageEvalInput("img2", ground_truth=gt, predictions=preds_exact[:3])
    summary = evaluate_predictions([item1, item2], count_tolerance_ratio=0.25)
    assert summary.num_images == 2
    assert summary.count_mae == 0.5
    assert summary.count_mape_pct == 12.5
    assert summary.exact_within_tolerance_pct == 100.0


def test_evaluate_by_density_buckets() -> None:
    """Shelves are partitioned into sparse (<50), medium (50-150), and dense (>150)."""
    assert density_bucket(20) == "sparse (<50)"
    assert density_bucket(100) == "medium (50-150)"
    assert density_bucket(220) == "dense (>150)"

    sparse_gt = tuple(DetectionBox(i * 10, 0, i * 10 + 8, 10) for i in range(10))
    dense_gt = tuple(DetectionBox((i % 20) * 10, (i // 20) * 12, (i % 20) * 10 + 8, (i // 20) * 12 + 10) for i in range(160))

    breakdown = evaluate_by_density(
        [
            ImageEvalInput("s", sparse_gt, sparse_gt),
            ImageEvalInput("d", dense_gt, dense_gt[:-8]),
        ]
    )
    assert breakdown["sparse (<50)"].num_images == 1
    assert breakdown["sparse (<50)"].count_mae == 0.0
    assert breakdown["medium (50-150)"].num_images == 0
    assert breakdown["dense (>150)"].num_images == 1
    assert breakdown["dense (>150)"].count_mae == 8.0
