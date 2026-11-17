"""Negative-control tests for detection evaluation and ONNX plausibility.

Verifies that:
1. A randomly initialised box generator scores near-zero mAP (< 0.05) on real shelf layouts.
2. Shuffling predictions across mismatched coordinates scores near-zero mAP (< 0.05).
3. `verify_onnx_model_plausibility` rejects undersized or constant-output ONNX files.
4. `bootstrap_confidence_intervals` and `compute_ap50_95` compute honest intervals.
"""
from __future__ import annotations

from pathlib import Path
import random
import pytest

from shelfsense_training.metrics import (
    DetectionBox,
    ImageEvalInput,
    bootstrap_confidence_intervals,
    compute_ap50,
    compute_ap50_95,
    verify_onnx_model_plausibility,
)


def _real_shelf_ground_truth() -> list[ImageEvalInput]:
    """Builds a dense 120-item shelf layout across 5 rows (1920x1080)."""
    gts: list[DetectionBox] = []
    for row in range(5):
        y1 = 80.0 + row * 190.0
        for col in range(24):
            x1 = 40.0 + col * 76.0
            gts.append(DetectionBox(x1, y1, x1 + 52.0, y1 + 140.0, 1.0))
    return [ImageEvalInput("shelf_dense_1", tuple(gts), ())]


def test_negative_control_random_boxes_score_near_zero_map() -> None:
    """Randomly generated boxes on a 1920x1080 shelf score near-zero mAP50 (< 0.05)."""
    rng = random.Random(12345)
    base = _real_shelf_ground_truth()[0]
    random_preds: list[DetectionBox] = []
    for _ in range(120):
        x1 = rng.uniform(0.0, 1800.0)
        y1 = rng.uniform(0.0, 950.0)
        w = rng.uniform(10.0, 300.0)
        h = rng.uniform(10.0, 300.0)
        random_preds.append(DetectionBox(x1, y1, x1 + w, y1 + h, score=rng.uniform(0.1, 0.99)))

    eval_item = ImageEvalInput(base.image_id, base.ground_truth, tuple(random_preds))
    ap50 = compute_ap50([eval_item])
    ap50_95 = compute_ap50_95([eval_item])
    assert ap50 < 0.05, f"Random predictions scored implausibly high mAP50: {ap50}"
    assert ap50_95 < 0.03, f"Random predictions scored implausibly high mAP50:95: {ap50_95}"


def test_negative_control_shuffled_predictions_score_near_zero_map() -> None:
    """Shuffling box coordinates across an image destroys alignment and scores near-zero mAP."""
    rng = random.Random(99)
    base = _real_shelf_ground_truth()[0]
    xs = [b.x1 for b in base.ground_truth]
    ys = [b.y1 for b in base.ground_truth]
    rng.shuffle(xs)
    rng.shuffle(ys)
    # Offset by half a shelf bay so shuffled boxes land in unrelated locations.
    shuffled = tuple(
        DetectionBox((x + 317.0) % 1800.0, (y + 293.0) % 920.0, ((x + 317.0) % 1800.0) + 18.0, ((y + 293.0) % 920.0) + 22.0, 0.8)
        for x, y in zip(xs, ys)
    )
    eval_item = ImageEvalInput(base.image_id, base.ground_truth, shuffled)
    assert compute_ap50([eval_item]) < 0.05


def test_onnx_plausibility_rejects_tiny_files(tmp_path: Path) -> None:
    """An ONNX file under 4 MB or with <1M parameters is rejected as implausible."""
    tiny_onnx = tmp_path / "tiny_fake.onnx"
    tiny_onnx.write_bytes(b"not-a-real-detector" * 100)
    with pytest.raises(ValueError, match="below minimum plausible detector size"):
        verify_onnx_model_plausibility(str(tiny_onnx))


def test_bootstrap_confidence_intervals_and_ap50_95() -> None:
    """Bootstrap 95% CI brackets the sample mean and reflects sample variance across images."""
    gt = (DetectionBox(10, 10, 50, 50), DetectionBox(70, 10, 110, 50))
    good = ImageEvalInput("img_good", gt, gt)
    miss = ImageEvalInput("img_miss", gt, (gt[0],))
    ci = bootstrap_confidence_intervals([good, miss], n_resamples=200, seed=42)
    assert 0.4 <= ci["map50"][0] <= ci["map50"][1] <= 1.0
    assert ci["count_mae"][0] <= 0.5 <= ci["count_mae"][1]
