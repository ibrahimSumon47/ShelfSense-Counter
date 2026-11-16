"""Annotation converters and dataset loader for ShelfSense.

Unifies SKU-110K CSV annotations, Supermarket Shelves (Supervisely / Pascal VOC / COCO),
and Grocery Dataset text annotations into a single-class (`class_id = 0`, label `item`)
representation with export to YOLO `.txt` and COCO `.json`.
"""
from __future__ import annotations

import csv
import io
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class BoundingBox:
    """Axis-aligned pixel bounding box clamped to image boundaries."""

    x1: float
    y1: float
    x2: float
    y2: float
    class_id: int = 0

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    def to_yolo(self, image_width: int, image_height: int) -> tuple[int, float, float, float, float]:
        """Returns (class_id, x_center, y_center, width, height) normalized to [0, 1]."""
        if image_width <= 0 or image_height <= 0:
            raise ValueError(f"Invalid image dimensions: {image_width}x{image_height}")
        xc = ((self.x1 + self.x2) / 2.0) / image_width
        yc = ((self.y1 + self.y2) / 2.0) / image_height
        w = self.width / image_width
        h = self.height / image_height
        return (
            self.class_id,
            min(1.0, max(0.0, xc)),
            min(1.0, max(0.0, yc)),
            min(1.0, max(0.0, w)),
            min(1.0, max(0.0, h)),
        )


@dataclass(frozen=True)
class AnnotatedImage:
    """An image and its validated product bounding boxes."""

    image_name: str
    width: int
    height: int
    boxes: tuple[BoundingBox, ...]


def clamp_box(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    image_width: int,
    image_height: int,
    min_side: float = 2.0,
) -> BoundingBox | None:
    """Clamps pixel coordinates to [0, W] x [0, H] and drops degenerate boxes."""
    cx1 = max(0.0, min(float(image_width), float(x1)))
    cy1 = max(0.0, min(float(image_height), float(y1)))
    cx2 = max(0.0, min(float(image_width), float(x2)))
    cy2 = max(0.0, min(float(image_height), float(y2)))
    if cx2 - cx1 < min_side or cy2 - cy1 < min_side:
        return None
    return BoundingBox(x1=cx1, y1=cy1, x2=cx2, y2=cy2, class_id=0)


def parse_sku110k_csv(csv_text_or_lines: str | Iterable[str]) -> list[AnnotatedImage]:
    """Parses SKU-110K headerless CSV rows into grouped AnnotatedImage records.

    Columns: image_name, x1, y1, x2, y2, class_name, image_width, image_height.
    Invalid or zero-area boxes are filtered out automatically.
    """
    if isinstance(csv_text_or_lines, str):
        reader = csv.reader(io.StringIO(csv_text_or_lines))
    else:
        reader = csv.reader(csv_text_or_lines)

    dims: dict[str, tuple[int, int]] = {}
    boxes_by_img: dict[str, list[BoundingBox]] = {}

    for row in reader:
        if not row or len(row) < 8:
            continue
        # Skip optional header row if present in community mirrors.
        if row[1].strip().lower() in {"x1", "xmin"}:
            continue
        img_name = row[0].strip()
        try:
            x1, y1, x2, y2 = float(row[1]), float(row[2]), float(row[3]), float(row[4])
            w, h = int(float(row[6])), int(float(row[7]))
        except ValueError:
            continue
        if w <= 0 or h <= 0:
            continue
        dims[img_name] = (w, h)
        boxes_by_img.setdefault(img_name, [])
        box = clamp_box(x1, y1, x2, y2, w, h)
        if box is not None:
            boxes_by_img[img_name].append(box)

    return [
        AnnotatedImage(
            image_name=name,
            width=dims[name][0],
            height=dims[name][1],
            boxes=tuple(boxes_by_img[name]),
        )
        for name in sorted(dims)
    ]


# Classes in multi-class shelf datasets that represent actual products (not price tags).
_PRODUCT_LABELS = {"product", "item", "object", "package", "bottle", "can", "box"}


def parse_supervisely_annotation(image_name: str, payload: dict) -> AnnotatedImage:
    """Parses a Supervisely per-image JSON annotation (used by Humans in the Loop).

    Keeps only product classes (excluding 'Price' tags) so counts reflect shelf stock.
    """
    size = payload.get("size", {})
    width = int(size.get("width", 0))
    height = int(size.get("height", 0))
    if width <= 0 or height <= 0:
        raise ValueError(f"Supervisely JSON for {image_name!r} has invalid size: {size}")

    boxes: list[BoundingBox] = []
    for obj in payload.get("objects", []):
        label = str(obj.get("classTitle", "")).strip().lower()
        if label and label not in _PRODUCT_LABELS:
            continue
        exterior = obj.get("points", {}).get("exterior", [])
        if len(exterior) < 2:
            continue
        xs = [float(pt[0]) for pt in exterior]
        ys = [float(pt[1]) for pt in exterior]
        box = clamp_box(min(xs), min(ys), max(xs), max(ys), width, height)
        if box is not None:
            boxes.append(box)

    return AnnotatedImage(image_name=image_name, width=width, height=height, boxes=tuple(boxes))


def parse_voc_xml(xml_text: str) -> AnnotatedImage:
    """Parses a Pascal VOC XML annotation, keeping only product boxes."""
    root = ET.fromstring(xml_text)
    filename = (root.findtext("filename") or "unknown.jpg").strip()
    size_el = root.find("size")
    if size_el is None:
        raise ValueError(f"VOC XML for {filename!r} is missing <size>")
    width = int(float(size_el.findtext("width", "0")))
    height = int(float(size_el.findtext("height", "0")))

    boxes: list[BoundingBox] = []
    for obj in root.findall("object"):
        name = (obj.findtext("name") or "").strip().lower()
        if name and name not in _PRODUCT_LABELS:
            continue
        bnd = obj.find("bndbox")
        if bnd is None:
            continue
        x1 = float(bnd.findtext("xmin", "0"))
        y1 = float(bnd.findtext("ymin", "0"))
        x2 = float(bnd.findtext("xmax", "0"))
        y2 = float(bnd.findtext("ymax", "0"))
        box = clamp_box(x1, y1, x2, y2, width, height)
        if box is not None:
            boxes.append(box)

    return AnnotatedImage(image_name=filename, width=width, height=height, boxes=tuple(boxes))


def format_yolo_lines(record: AnnotatedImage) -> list[str]:
    """Formats an AnnotatedImage as normalized YOLO `.txt` lines."""
    lines: list[str] = []
    for box in record.boxes:
        cid, xc, yc, w, h = box.to_yolo(record.width, record.height)
        lines.append(f"{cid} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")
    return lines


def export_coco_dict(records: Sequence[AnnotatedImage]) -> dict:
    """Converts a sequence of AnnotatedImage records into a COCO detection dictionary."""
    images = []
    annotations = []
    ann_id = 1

    for img_id, rec in enumerate(records, start=1):
        images.append(
            {
                "id": img_id,
                "file_name": rec.image_name,
                "width": rec.width,
                "height": rec.height,
            }
        )
        for box in rec.boxes:
            annotations.append(
                {
                    "id": ann_id,
                    "image_id": img_id,
                    "category_id": 1,
                    "bbox": [round(box.x1, 2), round(box.y1, 2), round(box.width, 2), round(box.height, 2)],
                    "area": round(box.area, 2),
                    "iscrowd": 0,
                }
            )
            ann_id += 1

    return {
        "images": images,
        "annotations": annotations,
        "categories": [{"id": 1, "name": "item", "supercategory": "retail"}],
    }


def compute_density_summary(records: Sequence[AnnotatedImage]) -> dict[str, float | int]:
    """Computes item-count statistics across a split for data card and evaluation reports."""
    if not records:
        return {"images": 0, "total_boxes": 0, "mean_per_image": 0.0, "min_per_image": 0, "max_per_image": 0}
    counts = [len(r.boxes) for r in records]
    total = sum(counts)
    return {
        "images": len(records),
        "total_boxes": total,
        "mean_per_image": round(total / len(records), 2),
        "min_per_image": min(counts),
        "max_per_image": max(counts),
    }


def write_yolo_dataset(records: Sequence[AnnotatedImage], labels_dir: Path) -> int:
    """Writes one `<stem>.txt` YOLO label file per image into labels_dir."""
    labels_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for rec in records:
        stem = Path(rec.image_name).stem
        out_path = labels_dir / f"{stem}.txt"
        lines = format_yolo_lines(rec)
        out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        written += 1
    return written


def write_coco_json(records: Sequence[AnnotatedImage], output_path: Path) -> None:
    """Writes a COCO JSON file for the given records."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = export_coco_dict(records)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
