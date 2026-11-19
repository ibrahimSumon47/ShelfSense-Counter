"""Count and accuracy regression on fixed images that were never trained on.

The images and the expectations ship as a release asset (`shelfsense-regression-v1.tar.gz`),
because datasets do not go into git. CI downloads the bundle and the published ONNX file into
`training/fixtures/shelfsense-regression-v1/` and runs this test.

Two checks, because they catch different breakage: per-image counts catch a changed score
threshold, NMS or a missing/doubled detection, and the mAP50 check catches boxes that moved
without changing how many there are (a broken anchor-centre offset leaves the count identical).
Tolerances are documented in the bundle itself.

Skipped when the bundle has not been downloaded, so the suite still runs on a fresh clone.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "shelfsense-regression-v1"
MODEL_PATH = FIXTURE_DIR / "model.onnx"
EXPECTED_PATH = FIXTURE_DIR / "expected.json"

MAP50_TOLERANCE = 0.03


def _bundle() -> dict:
    """Reads the expectations file the packager wrote."""
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


@pytest.mark.skipif(
    not (MODEL_PATH.is_file() and EXPECTED_PATH.is_file()),
    reason="regression bundle not downloaded (release asset shelfsense-regression-v1.tar.gz)",
)
def test_fixed_image_counts_and_map_stay_within_tolerance() -> None:
    """Both the per-image counts and mAP50 must stay inside the published tolerances."""
    from PIL import Image

    from shelfsense_training.coco_eval import coco_ap
    from shelfsense_training.converters import AnnotatedImage, BoundingBox
    from shelfsense_training.onnx_eval import make_session, run_raw_candidates, to_eval_inputs

    bundle = _bundle()
    cases = bundle["images"]
    assert cases, "the regression bundle lists no images"

    decoding = bundle.get("decoding", {})
    input_size = int(decoding.get("input_size", 640))
    samples = []
    for case in cases:
        path = FIXTURE_DIR / "images" / case["image"]
        with Image.open(path) as image:
            width, height = image.size
        boxes = tuple(BoundingBox(float(b[0]), float(b[1]), float(b[2]), float(b[3]), 0) for b in case["ground_truth"])
        samples.append((path, AnnotatedImage(case["image"], width, height, boxes)))

    session = make_session(MODEL_PATH)
    cached = run_raw_candidates(
        session,
        samples,
        input_size,
        normalise=decoding.get("normalise", "no") == "yes",
        center_fix=decoding.get("center_fix", "none"),
    )
    eval_inputs = to_eval_inputs(
        samples,
        cached,
        input_size,
        float(decoding.get("score_thresh", 0.3)),
        float(decoding.get("nms_thresh", 0.35)),
        int(decoding.get("max_dets", 1000)),
    )
    counts = {item.image_id: len(item.predictions) for item in eval_inputs}

    failures = []
    for case in cases:
        expected = int(case["expected_count"])
        actual = counts[case["image"]]
        if abs(actual - expected) > int(case["tolerance"]):
            failures.append(f"count {case['image']}: expected {expected} +-{case['tolerance']}, got {actual}")

    expected_map50 = bundle.get("expected_map50")
    if expected_map50 is not None:
        measured = coco_ap(eval_inputs)["map50"]
        if abs(measured - float(expected_map50)) > MAP50_TOLERANCE:
            failures.append(
                f"mAP50: expected {float(expected_map50):.4f} +-{MAP50_TOLERANCE}, got {measured:.4f}"
            )

    assert not failures, "regression beyond tolerance:\n" + "\n".join(failures)
