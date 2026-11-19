"""Unit tests for the ONNX decoding path shared by evaluation, the CLI and the browser."""
import numpy as np
import pytest

from shelfsense_training.onnx_eval import (
    decode_raw,
    legacy_center_fix,
    level_sizes,
    nms_numpy,
)


def test_level_sizes_requires_multiple_of_128() -> None:
    """FCOS anchor centres only land on exact strides for multiples of 128."""
    assert level_sizes(640) == [(80, 8), (40, 16), (20, 32), (10, 64), (5, 128)]
    with pytest.raises(ValueError):
        level_sizes(650)


def test_nms_keeps_highest_scoring_and_removes_overlaps() -> None:
    """Two heavily overlapping boxes collapse to one; a distant box survives."""
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], dtype=np.float32)
    scores = np.array([0.9, 0.8, 0.7], dtype=np.float32)
    kept = nms_numpy(boxes, scores, 0.45)
    assert kept.tolist() == [0, 2]


def test_decode_raw_thresholds_caps_and_rescales() -> None:
    """Candidates below the score threshold are dropped, and boxes are mapped back to original pixels."""
    # One candidate at score 0.9 covering a 100x100 box centred at (320, 320) in a 640 input.
    raw = np.zeros((1, 2, 6), dtype=np.float32)
    raw[0, 0] = [320, 320, 100, 100, 0.9, 1.0]
    raw[0, 1] = [320, 320, 100, 100, 0.05, 1.0]
    boxes, scores = decode_raw(raw, 640, 1280, 960, score_thresh=0.25, nms_thresh=0.45, max_dets=1000)
    assert boxes.shape == (1, 4)
    assert scores.tolist() == pytest.approx([0.9])
    # x scaled by 1280/640 = 2, y by 960/640 = 1.5.
    assert boxes[0].tolist() == pytest.approx([540.0, 405.0, 740.0, 555.0])


def test_decode_raw_respects_max_dets_cap() -> None:
    """The cap used for reporting is applied at decode time, exactly as the model's postprocessor would."""
    raw = np.zeros((1, 20, 6), dtype=np.float32)
    for i in range(20):
        raw[0, i] = [10.0 + i * 20, 10.0, 8.0, 8.0, 0.9, 1.0]
    boxes, scores = decode_raw(raw, 640, 640, 640, score_thresh=0.25, nms_thresh=0.45, max_dets=5)
    assert boxes.shape[0] == 5
    assert scores[0] >= scores[-1]


def test_legacy_center_fix_shifts_each_level_by_half_a_stride() -> None:
    """Exports that used (g+0.5)*stride are shifted back to torchvision's g*stride + stride/2 convention."""
    raw = np.zeros((1, 8525, 6), dtype=np.float32)
    raw[0, :, 0] = 100.0
    raw[0, :, 1] = 100.0
    fixed = legacy_center_fix(raw, 640)
    assert fixed[0, 0, 0] == pytest.approx(96.0)  # stride 8 -> minus 4
    assert fixed[0, 6400 + 1600, 0] == pytest.approx(84.0)  # stride 32 -> minus 16
    assert fixed[0, 6400 + 1600 + 400, 0] == pytest.approx(68.0)  # stride 64 -> minus 32


def test_coco_ap_counts_cap_at_100() -> None:
    """The 100-detection cap is visible in pycocotools recall, which is the cause of the count ceiling."""
    pytest.importorskip("pycocotools")
    from shelfsense_training.coco_eval import coco_ap
    from shelfsense_training.metrics import DetectionBox, ImageEvalInput

    gt = tuple(DetectionBox(x1=float(i * 20), y1=0.0, x2=float(i * 20 + 18), y2=18.0) for i in range(150))
    preds = tuple(DetectionBox(b.x1, b.y1, b.x2, b.y2, 0.9) for b in gt)
    one = ImageEvalInput("dense", gt, preds)

    uncapped = coco_ap([one], max_dets=1000)
    capped = coco_ap([one], max_dets=100)
    assert uncapped["num_dt"] == 150
    assert capped["num_dt"] == 100
    assert uncapped["map50"] > capped["map50"]
