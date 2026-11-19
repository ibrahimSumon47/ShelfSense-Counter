"""Packages a fixed image set and its expected counts for the count-regression test.

The fixture images come from the CC0 test split and the SKU-110K test subset, neither of which
was trained on, and they ship as a release asset because datasets never go into git. The
expected counts are what the published ONNX model produced when it was evaluated, so the test
catches a broken export, a changed decoder or a swapped file rather than a small accuracy move.
"""
from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path

TOLERANCE_RATIO = 0.10
TOLERANCE_MIN_ITEMS = 5


def collect(samples, predictions_payload: dict, limit: int) -> list[dict]:
    """Pairs each sample with the predicted count and its tolerance from a prediction file."""
    predicted = {image["image_id"]: image for image in predictions_payload["images"]}
    rows = []
    for path, ann in samples:
        image = predicted.get(ann.image_name)
        if image is None:
            continue
        count = len(image["predictions"])
        rows.append(
            {
                "image": ann.image_name,
                "source_path": str(path),
                "width": ann.width,
                "height": ann.height,
                # Ground truth travels with the bundle so the test can recompute mAP, not only counts.
                "ground_truth": image["ground_truth"],
                "predictions": image["predictions"],
                "ground_truth_count": len(ann.boxes),
                "expected_count": count,
                "tolerance": max(TOLERANCE_MIN_ITEMS, round(count * TOLERANCE_RATIO)),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def compute_map50(rows: list[dict]) -> float:
    """mAP50 of the bundle's own boxes, so the test can catch boxes that moved without changing counts."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from shelfsense_training.coco_eval import coco_ap
    from shelfsense_training.metrics import DetectionBox, ImageEvalInput

    inputs = []
    for row in rows:
        gt = tuple(DetectionBox(float(b[0]), float(b[1]), float(b[2]), float(b[3]), 1.0) for b in row["ground_truth"])
        preds = tuple(DetectionBox(float(b[0]), float(b[1]), float(b[2]), float(b[3]), float(b[4])) for b in row["predictions"])
        inputs.append(ImageEvalInput(row["image"], gt, preds))
    return float(coco_ap(inputs)["map50"])


def write_bundle(
    rows: list[dict],
    out_dir: Path,
    params: dict | None = None,
    map50: float | None = None,
    name: str = "shelfsense-regression-v1",
) -> dict:
    """Copies the images next to an expectations file and tars both (release asset, not git)."""
    images_dir = out_dir / f"{name}-images"
    images_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        source = Path(row.pop("source_path"))
        target = images_dir / row["image"]
        if source.resolve() != target.resolve():
            target.write_bytes(source.read_bytes())

    expectations = out_dir / f"{name}-expected.json"
    expectations.write_text(
        json.dumps(
            {
                "tolerance_rule": f"+-max({TOLERANCE_MIN_ITEMS}, {int(TOLERANCE_RATIO * 100)}% of expected)",
                "expected_map50": map50,
                "decoding": params or {},
                "images": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    archive = out_dir / f"{name}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for row in rows:
            tar.add(images_dir / row["image"], arcname=f"images/{row['image']}")
        tar.add(expectations, arcname="expected.json")
    return {
        "archive": str(archive),
        "archive_bytes": archive.stat().st_size,
        "images": len(rows),
        "expectations": str(expectations),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the count-regression fixture bundle.")
    parser.add_argument("--predictions", type=Path, nargs="+", required=True, help="one gz per split")
    parser.add_argument("--cc0-dir", type=Path, required=True)
    parser.add_argument("--sku-test-dir", type=Path, default=None)
    parser.add_argument(
        "--cc0-splits",
        default="test,val,train",
        help="Comma-separated CC0 splits to draw from, in order. The test split is always first.",
    )
    parser.add_argument("--evaluation", type=Path, default=None, help="eval_onnx.py JSON, for the mAP50 expectation")
    parser.add_argument("--out-dir", type=Path, default=Path("training/fixtures"))
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)

    import gzip
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from shelfsense_training import data as ds

    payloads = []
    for path in args.predictions:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            payloads.append(json.load(fh))
    payload = payloads[0]
    merged = {**payload, "images": [img for p in payloads for img in p["images"]]}

    cc0_train, cc0_val, cc0_test, _leaks = ds.split_cc0(ds.load_cc0_supermarket(args.cc0_dir))
    by_split = {"train": cc0_train, "val": cc0_val, "test": cc0_test}
    rows = []
    for split in [s.strip() for s in args.cc0_splits.split(",") if s.strip()]:
        if len(rows) >= args.limit:
            break
        rows += collect(by_split.get(split, []), merged, limit=args.limit - len(rows))
    if len(rows) < args.limit and args.sku_test_dir:
        sku_test = ds.load_sku110k_split(args.sku_test_dir, "test", args.limit)
        rows += collect(sku_test, merged, limit=args.limit - len(rows))

    # The test rebuilds the decoder settings from this block, so the input size travels with them.
    decoding = dict(payload.get("params") or {})
    decoding["input_size"] = payload.get("input_size", 640)
    map50 = compute_map50(rows)
    if args.evaluation and args.evaluation.is_file():
        evaluation = json.loads(args.evaluation.read_text(encoding="utf-8"))
        map50 = evaluation["models"][0]["primary"]["map50"]
    summary = write_bundle(rows, args.out_dir, params=decoding, map50=map50)
    summary["splits"] = args.cc0_splits
    summary["ground_truth_items"] = sum(row["ground_truth_count"] for row in rows)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
