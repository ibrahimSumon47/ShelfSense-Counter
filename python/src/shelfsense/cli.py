"""Command-line interface for ShelfSense (`shelfsense count photo.jpg`)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

from shelfsense.detector import ShelfDetector


def build_parser() -> argparse.ArgumentParser:
    """Constructs the `shelfsense` CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="shelfsense",
        description="Count retail shelf products, detect empty gaps, and flag low stock.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    count_p = sub.add_parser("count", help="Analyze a shelf image and print the count and gaps.")
    count_p.add_argument("image", type=Path, help="Path to a shelf photo (.jpg, .png, .webp).")
    count_p.add_argument("--model", type=Path, default=None, help="Optional path to an ONNX model file.")
    count_p.add_argument("--threshold", type=int, default=10, help="Low-stock alert threshold (default: 10).")
    count_p.add_argument("--score-threshold", type=float, default=0.25, help="Detection confidence cutoff.")
    count_p.add_argument("--json", action="store_true", dest="as_json", help="Emit structured JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Runs the `shelfsense` CLI and returns an exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "count":
        image_path: Path = args.image
        if not image_path.is_file():
            print(f"Error: image file not found: {image_path}", file=sys.stderr)
            return 2

        if args.model is None:
            print(
                "WARNING: no --model given. Falling back to a non-learned contrast heuristic that only "
                "works on clean synthetic images. Counts are NOT a measurement of real shelves.",
                file=sys.stderr,
            )
        detector = ShelfDetector(
            model_path=args.model,
            score_threshold=args.score_threshold,
        )
        with Image.open(image_path) as img:
            result = detector.analyze(img, low_stock_threshold=args.threshold)

        if args.as_json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            status_str = "LOW STOCK" if result.low_stock else "OK"
            print(
                f"{image_path.name}: {result.count} items detected | "
                f"{len(result.gaps)} gaps (~{result.estimated_missing_total} missing) | "
                f"status: {status_str}"
            )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
