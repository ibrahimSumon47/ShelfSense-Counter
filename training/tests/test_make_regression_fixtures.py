"""Tests for the regression fixture packager."""
from __future__ import annotations

import json
import tarfile
from pathlib import Path

from PIL import Image

from make_regression_fixtures import collect, write_bundle
from shelfsense_training.converters import AnnotatedImage, BoundingBox


def _samples(tmp_path: Path) -> list:
    """Two tiny photos with ground truth boxes."""
    samples = []
    for name in ("a.jpg", "b.jpg"):
        path = tmp_path / name
        Image.new("RGB", (40, 20), color=(10, 10, 10)).save(path)
        samples.append((path, AnnotatedImage(name, 40, 20, (BoundingBox(1, 1, 9, 9, 0), BoundingBox(10, 1, 20, 9, 0)))))
    return samples


def _payload() -> dict:
    """Predictions that over-count a.jpg and under-count b.jpg."""
    return {
        "model_file": "model.onnx",
        "input_size": 640,
        "params": {"score_thresh": 0.3, "nms_thresh": 0.35, "max_dets": 1000, "normalise": "no", "center_fix": "none"},
        "images": [
            {"image_id": "a.jpg", "ground_truth": [[1, 1, 9, 9], [10, 1, 20, 9]], "predictions": [[1, 1, 9, 9, 0.9]] * 5},
            {"image_id": "b.jpg", "ground_truth": [[1, 1, 9, 9], [10, 1, 20, 9]], "predictions": [[1, 1, 9, 9, 0.9]] * 14},
        ],
    }


def test_collect_pairs_counts_and_tolerance(tmp_path: Path) -> None:
    """The 5-prediction image gets the minimum tolerance of 5, the 14-prediction one gets 5 too."""
    rows = collect(_samples(tmp_path), _payload(), limit=2)
    assert [row["image"] for row in rows] == ["a.jpg", "b.jpg"]
    assert [row["expected_count"] for row in rows] == [5, 14]
    # 10 % of 14 rounds to 1, so the floor of 5 items applies.
    assert [row["tolerance"] for row in rows] == [5, 5]
    assert rows[0]["ground_truth_count"] == 2
    assert len(rows[1]["ground_truth"]) == 2


def test_write_bundle_tars_images_and_expectations(tmp_path: Path) -> None:
    """The archive holds images/ plus expected.json and records the mAP50 expectation."""
    rows = collect(_samples(tmp_path), _payload(), limit=2)
    summary = write_bundle(rows, tmp_path / "out", params={"input_size": 640}, map50=0.51)

    archive = Path(summary["archive"])
    assert archive.is_file() and summary["images"] == 2
    with tarfile.open(archive) as tar:
        names = sorted(tar.getnames())
    assert names == ["expected.json", "images/a.jpg", "images/b.jpg"]

    expectations = json.loads((tmp_path / "out" / "shelfsense-regression-v1-expected.json").read_text(encoding="utf-8"))
    assert expectations["expected_map50"] == 0.51
    assert expectations["decoding"] == {"input_size": 640}
    assert [row["image"] for row in expectations["images"]] == ["a.jpg", "b.jpg"]
    assert "source_path" not in expectations["images"][0]
