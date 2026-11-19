"""Count regression on 20 fixed images that were never trained on.

The images and the expectations ship as a release asset (`shelfsense-regression-v1.tar.gz`),
because datasets do not go into git. CI downloads the bundle and the published ONNX file into
`training/fixtures/shelfsense-regression-v1/` and runs this test, which fails if the decoder,
the export or the model file changes the counts by more than the tolerance.

Skipped when the bundle has not been downloaded, so the suite still runs on a fresh clone.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "shelfsense-regression-v1"
MODEL_PATH = FIXTURE_DIR / "model.onnx"
EXPECTED_PATH = FIXTURE_DIR / "expected.json"


def _load_cases() -> list[dict]:
    """Reads the expectations file the packager wrote."""
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))["images"]


@pytest.mark.skipif(
    not (MODEL_PATH.is_file() and EXPECTED_PATH.is_file()),
    reason="regression bundle not downloaded (release asset shelfsense-regression-v1.tar.gz)",
)
def test_fixed_image_counts_stay_within_tolerance() -> None:
    """Every fixed image must stay within its documented tolerance of the published count."""
    from PIL import Image

    from shelfsense_training.data import AnnotatedImage
    from shelfsense_training.onnx_eval import make_session, run_raw_candidates, to_eval_inputs

    cases = _load_cases()
    assert len(cases) == 20, f"the regression bundle should hold 20 images, found {len(cases)}"

    decoding = json.loads(EXPECTED_PATH.read_text(encoding="utf-8")).get("decoding", {})
    input_size = int(decoding.get("input_size", 640))
    samples = []
    for case in cases:
        path = FIXTURE_DIR / "images" / case["image"]
        with Image.open(path) as image:
            width, height = image.size
        samples.append((path, AnnotatedImage(case["image"], width, height, ())))

    session = make_session(MODEL_PATH)
    cached = run_raw_candidates(
        session,
        samples,
        input_size,
        normalise=decoding.get("normalise", "no") == "yes",
        center_fix=decoding.get("center_fix", "none"),
    )
    counts = {}
    for (path, ann), (raw, ow, oh) in zip(samples, cached):
        fresh = [(path, AnnotatedImage(ann.image_name, ow, oh, ()))]
        decoded = to_eval_inputs(
            fresh,
            [(raw, ow, oh)],
            input_size,
            float(decoding.get("score_thresh", 0.3)),
            float(decoding.get("nms_thresh", 0.35)),
            int(decoding.get("max_dets", 1000)),
        )
        counts[ann.image_name] = len(decoded[0].predictions)

    failures = []
    for case in cases:
        expected = int(case["expected_count"])
        actual = counts[case["image"]]
        if abs(actual - expected) > int(case["tolerance"]):
            failures.append(f"{case['image']}: expected {expected} +-{case['tolerance']}, got {actual}")
    assert not failures, "count regression beyond tolerance:\n" + "\n".join(failures)
