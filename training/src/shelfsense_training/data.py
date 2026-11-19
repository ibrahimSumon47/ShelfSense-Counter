"""Dataset loading helpers shared by training and evaluation (no torch import).

Layouts supported:
  - CC0 Supermarket Shelves (Supervisely JSON per image).
  - SKU-110K as mirrored on Kaggle: SKU110K_fixed/images/<split>/*.jpg with
    SKU110K_fixed/labels/<split>/*.txt in normalised YOLO format.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from shelfsense_training.converters import AnnotatedImage, BoundingBox, parse_supervisely_annotation
from shelfsense_training.splits import (
    ImageRecord,
    assign_leak_free_splits,
    compute_dhash,
    find_cross_split_leak_pairs,
    infer_source_group,
)

Sample = tuple[Path, AnnotatedImage]


def _scan_cc0_folder(root: Path) -> list[Sample]:
    """Parses every Supervisely annotation under `root` and pairs it with its image."""
    items: list[Sample] = []
    if not root.exists():
        return items
    img_by_name = {
        p.name: p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    }
    for ann_path in sorted(p for p in root.rglob("*.json") if p.name != "meta.json"):
        try:
            payload = json.loads(ann_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if "size" not in payload or "objects" not in payload:
            continue
        stem = ann_path.name[:-5] if ann_path.name.endswith(".json") else ann_path.stem
        img_path = img_by_name.get(stem)
        if img_path is None:
            img_path = next((img_by_name[stem + e] for e in (".jpg", ".jpeg", ".png") if stem + e in img_by_name), None)
        if img_path is None:
            continue
        rec = parse_supervisely_annotation(img_path.name, payload)
        if rec.boxes:
            items.append((img_path, rec))
    return items


def load_cc0_supermarket(cc0_root: Path) -> list[Sample]:
    """Loads the 45 CC0 images; falls back to scanning /kaggle/input when mounted elsewhere."""
    items = _scan_cc0_folder(cc0_root)
    if not items and Path("/kaggle/input").is_dir():
        items = _scan_cc0_folder(Path("/kaggle/input"))
    return items


def split_cc0(items: list[Sample], seed_ratios=(0.60, 0.20, 0.20)) -> tuple[list[Sample], list[Sample], list[Sample], int]:
    """Leak-free train/val/test split of the CC0 set (dHash groups). Returns the leak count too."""
    by_name = {ann.image_name: (p, ann) for p, ann in items}
    records = []
    for path, ann in items:
        with Image.open(path) as im:
            digest = compute_dhash(im)
        records.append(ImageRecord(ann.image_name, infer_source_group("supermarket_shelves", ann.image_name), digest))
    splits = assign_leak_free_splits(records, ratios=seed_ratios, max_hamming=8)
    leaks = len(find_cross_split_leak_pairs(records, splits, max_hamming=8))
    pick = lambda s: [by_name[k] for k, v in sorted(splits.items()) if v == s]  # noqa: E731
    return pick("train"), pick("val"), pick("test"), leaks


def load_sku110k_split(sku_root: Path, split: str, max_images: int) -> list[Sample]:
    """Loads up to `max_images` SKU-110K images of `split` (sorted by file name, deterministic)."""
    if not sku_root.exists() and Path("/kaggle/input").is_dir():
        sku_root = Path("/kaggle/input")
    if not sku_root.exists() or max_images <= 0:
        return []
    img_dirs = [p for p in sku_root.rglob(f"images/{split}") if p.is_dir()]
    lbl_dirs = [p for p in sku_root.rglob(f"labels/{split}") if p.is_dir()]
    if not img_dirs or not lbl_dirs:
        return []
    results: list[Sample] = []
    for img_p in sorted(img_dirs[0].glob(f"{split}_*.jpg"))[:max_images]:
        lbl_p = lbl_dirs[0] / f"{img_p.stem}.txt"
        if not lbl_p.is_file():
            continue
        try:
            with Image.open(img_p) as im:
                w, h = im.size
        except OSError:
            continue
        boxes: list[BoundingBox] = []
        for line in lbl_p.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            try:
                xc, yc, bw, bh = (float(parts[1]) * w, float(parts[2]) * h, float(parts[3]) * w, float(parts[4]) * h)
            except ValueError:
                continue
            x1, y1 = max(0.0, xc - bw / 2), max(0.0, yc - bh / 2)
            x2, y2 = min(float(w), xc + bw / 2), min(float(h), yc + bh / 2)
            if x2 - x1 >= 2.0 and y2 - y1 >= 2.0:
                boxes.append(BoundingBox(x1, y1, x2, y2, 0))
        if boxes:
            results.append((img_p, AnnotatedImage(img_p.name, w, h, tuple(boxes))))
    return results


def load_square_uint8(path: Path, size: int) -> tuple[np.ndarray, int, int]:
    """Decodes an image and stretches it to size x size, the training preprocessing.

    Returns (HxWx3 uint8 RGB, original_width, original_height). The full image is decoded:
    PIL's JPEG draft mode was tried first and changed predictions enough to break agreement
    with the PyTorch evaluation, so faithfulness won over speed.
    """
    with Image.open(path) as im:
        orig_w, orig_h = im.size
        rgb = im.convert("RGB").resize((size, size), Image.Resampling.BILINEAR)
    return np.asarray(rgb, dtype=np.uint8), orig_w, orig_h
