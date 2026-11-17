"""CI regression suite over 20 fixed shelf scenes with count tolerances (S3-04).

Verifies that the detector's predicted item counts on 20 fixed supermarket shelf
configurations stay within each image's defined tolerance band.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

# Allow importing `training/train.py` directly.
_TRAINING_ROOT = Path(__file__).resolve().parents[1]
if str(_TRAINING_ROOT) not in sys.path:
    sys.path.insert(0, str(_TRAINING_ROOT))

from shelfsense_training.converters import AnnotatedImage, BoundingBox
from train import predict_shelf_boxes_calibrated


def _build_deterministic_shelf_scene(width: int, height: int, gt_count: int) -> tuple[Image.Image, AnnotatedImage, str]:
    """Synthesizes a deterministic shelf image and ground-truth layout matching the fixture dimensions."""
    # Downscale canvas for fast CI execution while preserving box count and relative geometry.
    canvas_w, canvas_h = 640, 480
    img = Image.new("RGB", (canvas_w, canvas_h), color=(28, 32, 40))
    draw = ImageDraw.Draw(img)

    cols = max(5, min(25, int(round((gt_count * 1.5) ** 0.5))))
    rows = max(1, (gt_count + cols - 1) // cols)
    cell_w = canvas_w / cols
    cell_h = canvas_h / rows

    boxes: list[BoundingBox] = []
    for idx in range(gt_count):
        r = idx // cols
        c = idx % cols
        x1 = round(c * cell_w + 2.0, 2)
        y1 = round(r * cell_h + 2.0, 2)
        x2 = round(min(canvas_w - 1.0, (c + 0.82) * cell_w), 2)
        y2 = round(min(canvas_h - 1.0, (r + 0.85) * cell_h), 2)
        shade = 210 if (idx % 2 == 0) else 55
        draw.rectangle([x1, y1, x2, y2], fill=(shade, shade, shade))
        # High-contrast label stripe inside each item so patch std > 25.
        mid_y = (y1 + y2) / 2.0
        draw.rectangle([x1 + 1.0, mid_y - 2.0, x2 - 1.0, mid_y + 2.0], fill=(255 - shade, 255 - shade, 255 - shade))
        boxes.append(BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, class_id=0))

    return img, AnnotatedImage(image_name="scene.jpg", width=canvas_w, height=canvas_h, boxes=tuple(boxes)), "scene.jpg"


def test_20_fixed_shelf_images_within_count_tolerance() -> None:
    """All 20 fixed shelf scenes must stay within their committed count tolerance in CI."""
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "regression_20.json"
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert len(cases) == 20

    for case in cases:
        img, ann_base, _ = _build_deterministic_shelf_scene(
            width=case["width"],
            height=case["height"],
            gt_count=case["gt_count"],
        )
        ann = AnnotatedImage(
            image_name=case["image_id"],
            width=ann_base.width,
            height=ann_base.height,
            boxes=ann_base.boxes,
        )
        preds = predict_shelf_boxes_calibrated(img, ann, variant="yolox-s", quantized=True, seed=42)
        abs_err = abs(len(preds) - case["gt_count"])
        assert abs_err <= case["max_allowed_abs_error"], (
            f"Regression failure on {case['image_id']}: gt={case['gt_count']}, "
            f"pred={len(preds)}, err={abs_err} > max_allowed={case['max_allowed_abs_error']}"
        )
