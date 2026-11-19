"""Renders a failure-case gallery from a saved prediction file.

Reads the gzipped predictions written by `training/eval_onnx.py --predictions-dir` and draws
ground-truth boxes in one colour and predicted boxes in another over the real photo, so the
worst count errors can be looked at instead of only scored. Images are downscaled for the
report; the boxes are scaled with them.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from PIL import Image, ImageDraw


def load_predictions(path: Path) -> dict:
    """Reads a prediction file produced by eval_onnx.py."""
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def rank_failures(payload: dict, limit: int = 3) -> list[dict]:
    """Orders images by absolute count error, worst first, and keeps `limit` of them."""
    images = []
    for image in payload["images"]:
        gt = len(image["ground_truth"])
        pred = len(image["predictions"])
        images.append(
            {
                "image_id": image["image_id"],
                "gt_count": gt,
                "pred_count": pred,
                "abs_error": abs(pred - gt),
                "pct_error": round(abs(pred - gt) / max(1, gt) * 100.0, 1),
            }
        )
    return sorted(images, key=lambda row: (-row["abs_error"], row["image_id"]))[:limit]


def draw_overlay(image_path: Path, entry: dict, output_path: Path, target_width: int = 900) -> dict:
    """Draws ground truth (green) and predictions (orange) on a downscaled copy of the photo."""
    with Image.open(image_path) as raw:
        photo = raw.convert("RGB")
    scale = target_width / float(photo.width)
    photo = photo.resize((target_width, max(1, round(photo.height * scale))), Image.Resampling.BILINEAR)
    draw = ImageDraw.Draw(photo)

    payload_images = entry["_image"]
    for box in payload_images["ground_truth"]:
        draw.rectangle([box[0] * scale, box[1] * scale, box[2] * scale, box[3] * scale], outline=(34, 197, 94), width=2)
    for box in payload_images["predictions"]:
        draw.rectangle([box[0] * scale, box[1] * scale, box[2] * scale, box[3] * scale], outline=(249, 115, 22), width=1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    photo.save(output_path, format="PNG", optimize=True)
    return {
        "image_id": entry["image_id"],
        "gt_count": entry["gt_count"],
        "pred_count": entry["pred_count"],
        "abs_error": entry["abs_error"],
        "pct_error": entry["pct_error"],
        "file": output_path.name,
        "file_bytes": output_path.stat().st_size,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render worst-case overlay images from a prediction file.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args(argv)

    payload = load_predictions(args.predictions)
    by_name = {image["image_id"]: image for image in payload["images"]}
    gallery = []
    for entry in rank_failures(payload, limit=args.limit):
        source = args.images_dir / entry["image_id"]
        if not source.is_file():
            print(f"missing image, skipped: {source}")
            continue
        gallery.append(draw_overlay(source, {**entry, "_image": by_name[entry["image_id"]]}, args.out_dir / f"{Path(entry['image_id']).stem}-overlay.png"))

    index = args.out_dir / "index.json"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(
        json.dumps({"model_file": payload.get("model_file"), "params": payload.get("params"), "gallery": gallery}, indent=2),
        encoding="utf-8",
    )
    for row in gallery:
        print(f"{row['image_id']}: gt={row['gt_count']} pred={row['pred_count']} error={row['pct_error']}% -> {row['file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
