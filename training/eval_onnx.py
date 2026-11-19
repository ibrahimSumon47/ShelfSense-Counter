"""Re-evaluate exported ONNX ShelfSense detectors on validation or test splits.

Why this exists: the first training runs were exported with torchvision's default
`detections_per_img=100`, which caps counts on dense shelves, and their metrics were
computed inside the training process with PyTorch. This script runs the ONNX files
themselves through the decoding the browser and the Python CLI use, then reports
pycocotools AP (with the detection cap stated) plus count error, so the effect of the
cap and of the score/NMS thresholds can be measured on validation.

Everything is measured from real model output. Nothing here perturbs predictions.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR / "src") not in sys.path:
    sys.path.insert(0, str(_THIS_DIR / "src"))

from shelfsense_training import data as ds
from shelfsense_training.coco_eval import coco_ap
from shelfsense_training.export import onnx_sha256
from shelfsense_training.metrics import (
    bootstrap_confidence_intervals,
    evaluate_by_density,
    evaluate_predictions,
)
from shelfsense_training.onnx_eval import make_session, run_raw_candidates, to_eval_inputs

REPO_ROOT = _THIS_DIR.parent


def load_split(args: argparse.Namespace) -> list:
    """Loads the requested CC0 or SKU-110K split with the same split code the trainer uses."""
    if args.dataset == "cc0":
        items = ds.load_cc0_supermarket(args.cc0_dir)
        train, val, test, leaks = ds.split_cc0(items)
        print(f"CC0 images={len(items)} train={len(train)} val={len(val)} test={len(test)} cross_split_leaks={leaks}")
        return {"train": train, "val": val, "test": test}[args.split]
    if args.dataset == "sku110k":
        limit = args.sku110k_test_subset if args.split == "test" else args.sku110k_val_subset
        return ds.load_sku110k_split(args.sku_dir, args.split, limit)
    raise ValueError(f"unknown dataset {args.dataset}")


def summarise_at(samples: list, cached: list, input_size: int, score_thresh: float, nms_thresh: float, max_dets: int):
    """Applies one threshold pair to cached candidates and reports every metric."""
    eval_inputs = to_eval_inputs(samples, cached, input_size, score_thresh, nms_thresh, max_dets)
    summary = evaluate_predictions(eval_inputs)
    coco = coco_ap(eval_inputs, max_dets=max_dets)
    row = {
        "score_thresh": score_thresh,
        "nms_thresh": nms_thresh,
        "max_dets": max_dets,
        "num_images": summary.num_images,
        "map50": coco["map50"],
        "map50_95": coco["map"],
        "pycocotools_map75": coco["map75"],
        "num_gt": coco["num_gt"],
        "num_dt": coco["num_dt"],
        "count_mae": summary.count_mae,
        "count_mape_pct": summary.count_mape_pct,
        "pred_count_total": sum(len(i.predictions) for i in eval_inputs),
        "gt_count_total": sum(len(i.ground_truth) for i in eval_inputs),
    }
    return row, eval_inputs


def predictions_payload(samples: list, eval_inputs: list, onnx_path: Path, input_size: int, params: dict) -> dict:
    """Builds a recomputable prediction file: ground truth and predicted boxes in original pixels."""
    images = []
    for (_path, ann), item in zip(samples, eval_inputs):
        images.append(
            {
                "image_id": item.image_id,
                "width": ann.width,
                "height": ann.height,
                "ground_truth": [[round(b.x1, 3), round(b.y1, 3), round(b.x2, 3), round(b.y2, 3)] for b in item.ground_truth],
                "predictions": [
                    [round(b.x1, 3), round(b.y1, 3), round(b.x2, 3), round(b.y2, 3), round(float(b.score), 5)]
                    for b in item.predictions
                ],
            }
        )
    return {
        "model_file": onnx_path.name,
        "input_size": input_size,
        "params": params,
        "note": "Predicted boxes come from this ONNX file; rerun pycocotools on this file to recompute the numbers.",
        "images": images,
    }


def write_gzip_json(path: Path, payload: dict) -> int:
    """Writes deterministic gzipped JSON and returns the file size in bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    with gzip.GzipFile(filename=str(path), mode="wb", mtime=0) as fh:
        fh.write(raw)
    return path.stat().st_size


def evaluate_model(path: Path, samples: list, args: argparse.Namespace) -> dict:
    """Runs one ONNX file over the split: latency, every detection cap, optional sweep."""
    session = make_session(path)
    started = time.perf_counter()
    cached = run_raw_candidates(session, samples, args.input_size, normalise=args.normalise == "yes", center_fix=args.center_fix)
    seconds = time.perf_counter() - started
    print(f"[{path.name}] {len(samples)} images in {seconds:.1f}s ({seconds / len(samples) * 1000:.0f} ms/image)")

    results = []
    for max_dets in args.max_dets:
        row, _ = summarise_at(samples, cached, args.input_size, args.score_thresh, args.nms_thresh, max_dets)
        results.append(row)
        print("  " + json.dumps(row))

    sweep = []
    if args.grid:
        score_values, nms_values = args.grid.split(":")
        for score_thresh in [float(s) for s in score_values.split(",")]:
            for nms_thresh in [float(n) for n in nms_values.split(",")]:
                row, _ = summarise_at(samples, cached, args.input_size, score_thresh, nms_thresh, max(args.max_dets))
                sweep.append(row)
                print(f"  sweep score={score_thresh} nms={nms_thresh} map50={row['map50']} mae={row['count_mae']}")

    primary_row, eval_inputs = summarise_at(
        samples, cached, args.input_size, args.score_thresh, args.nms_thresh, args.max_dets[0]
    )
    params = {
        "score_thresh": args.score_thresh,
        "nms_thresh": args.nms_thresh,
        "max_dets": args.max_dets[0],
        "normalise": args.normalise,
        "center_fix": args.center_fix,
    }
    predictions_file = None
    if args.predictions_dir:
        target = args.predictions_dir / f"{path.stem}-{args.dataset}-{args.split}.json.gz"
        size = write_gzip_json(target, predictions_payload(samples, eval_inputs, path, args.input_size, params))
        predictions_file = {"path": target.as_posix(), "size_bytes": size}
        print(f"  predictions -> {predictions_file['path']} ({size / 1024:.0f} KiB)")

    return {
        "onnx_file": path.name,
        "onnx_size_bytes": path.stat().st_size,
        "onnx_sha256": onnx_sha256(path),
        "ms_per_image": round(seconds / len(samples) * 1000.0, 1),
        "results": results,
        "threshold_sweep": sweep,
        "bootstrap_95_ci": bootstrap_confidence_intervals(eval_inputs, n_resamples=500, seed=42),
        "by_density": {
            name: {
                "num_images": value.num_images,
                "map50": value.map50,
                "count_mae": value.count_mae,
                "count_mape_pct": value.count_mape_pct,
            }
            for name, value in evaluate_by_density(eval_inputs).items()
        },
        "per_image": [
            {
                "image_id": item.image_id,
                "gt_count": len(item.ground_truth),
                "pred_count": len(item.predictions),
                "abs_error": abs(len(item.predictions) - len(item.ground_truth)),
            }
            for item in eval_inputs
        ],
        "predictions_file": predictions_file,
        "primary": primary_row,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate ONNX ShelfSense detectors with pycocotools.")
    parser.add_argument("--onnx", type=Path, nargs="+", required=True)
    parser.add_argument("--dataset", choices=["cc0", "sku110k"], default="cc0")
    parser.add_argument("--split", choices=["train", "val", "test"], default="val")
    parser.add_argument("--cc0-dir", type=Path, default=REPO_ROOT / "training/data/supermarket_shelves")
    parser.add_argument("--sku-dir", type=Path, default=REPO_ROOT / "training/data/sku110k_val")
    parser.add_argument("--sku110k-val-subset", type=int, default=200)
    parser.add_argument("--sku110k-test-subset", type=int, default=200)
    parser.add_argument("--input-size", type=int, default=640)
    parser.add_argument("--score-thresh", type=float, default=0.25)
    parser.add_argument("--nms-thresh", type=float, default=0.45)
    parser.add_argument("--max-dets", type=int, nargs="+", default=[1000])
    parser.add_argument("--grid", default="", help="Optional score:nms sweep, e.g. 0.15,0.25,0.35:0.35,0.45")
    parser.add_argument("--center-fix", choices=["none", "legacy"], default="none")
    parser.add_argument(
        "--normalise",
        choices=["yes", "no"],
        default="no",
        help="Apply ImageNet mean/std in numpy. Only the first exports need it (it was missing from their graph).",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--predictions-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    samples = load_split(args)
    if not samples:
        raise SystemExit(f"no images found for dataset={args.dataset} split={args.split}")

    models = [evaluate_model(path, samples, args) for path in args.onnx]

    payload = {
        "dataset": args.dataset,
        "split": args.split,
        "num_images": len(samples),
        "input_size": args.input_size,
        "command": "python training/eval_onnx.py " + " ".join(argv if argv is not None else sys.argv[1:]),
        "models": models,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
