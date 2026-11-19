"""Tests for the failure-gallery renderer."""
from pathlib import Path

from PIL import Image

from render_failures import draw_overlay, load_predictions, rank_failures


def _payload() -> dict:
    """Two images: one badly under-counted, one nearly right."""
    return {
        "model_file": "test.onnx",
        "images": [
            {
                "image_id": "a.jpg",
                "ground_truth": [[0, 0, 10, 10]] * 100,
                "predictions": [[0, 0, 10, 10, 0.9]] * 20,
            },
            {
                "image_id": "b.jpg",
                "ground_truth": [[0, 0, 10, 10]] * 30,
                "predictions": [[0, 0, 10, 10, 0.9]] * 28,
            },
        ],
    }


def test_rank_failures_orders_by_absolute_error() -> None:
    """The 80-item miss comes first, not the 2-item one."""
    ranked = rank_failures(_payload(), limit=2)
    assert [row["image_id"] for row in ranked] == ["a.jpg", "b.jpg"]
    assert ranked[0]["abs_error"] == 80
    assert ranked[0]["pct_error"] == 80.0


def test_draw_overlay_writes_png_and_scales_boxes(tmp_path: Path) -> None:
    """A 200 px wide photo becomes a 90 px wide (scale 0.45) report image."""
    photo = tmp_path / "shelf.jpg"
    Image.new("RGB", (200, 100), color=(40, 40, 40)).save(photo)
    payload = _payload()
    entry = {**rank_failures(payload, limit=1)[0], "_image": payload["images"][0]}

    result = draw_overlay(photo, entry, tmp_path / "out" / "shelf-overlay.png", target_width=90)
    written = tmp_path / "out" / "shelf-overlay.png"
    assert written.is_file()
    assert result["gt_count"] == 100
    with Image.open(written) as rendered:
        assert rendered.size == (90, 45)
    assert result["file_bytes"] > 0


def test_load_predictions_reads_gzip(tmp_path: Path) -> None:
    """The loader reads exactly the format eval_onnx.py writes."""
    import gzip
    import json

    path = tmp_path / "preds.json.gz"
    with gzip.GzipFile(filename=str(path), mode="wb", mtime=0) as fh:
        fh.write(json.dumps(_payload()).encode("utf-8"))
    assert load_predictions(path)["model_file"] == "test.onnx"
