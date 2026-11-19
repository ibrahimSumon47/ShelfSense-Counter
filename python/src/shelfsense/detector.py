"""ONNX Runtime shelf product detector, preprocessing, and count + gap analyzer.

The detector is a torchvision FCOS ResNet-50 FPN exported with its normalisation and anchor
decoding inside the graph. It returns dense candidates `[1, N, 6] = [xc, yc, w, h, score, 1]`
in input pixels; thresholding, NMS and the cap happen here in the same order as
`training/eval_onnx.py`, so the CLI and the browser count a photo the same way.
"""
from __future__ import annotations

import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image

from shelfsense.gaps import Box, ShelfGap, detect_shelf_gaps


@dataclass(frozen=True)
class ScanAnalysis:
    """Complete result of analyzing a single shelf image."""

    image_width: int
    image_height: int
    count: int
    low_stock: bool
    low_stock_threshold: int
    boxes: tuple[Box, ...]
    gaps: tuple[ShelfGap, ...]
    estimated_missing_total: int

    def to_dict(self) -> dict:
        return {
            "image_width": self.image_width,
            "image_height": self.image_height,
            "count": self.count,
            "low_stock": self.low_stock,
            "low_stock_threshold": self.low_stock_threshold,
            "estimated_missing_total": self.estimated_missing_total,
            "boxes": [
                {
                    "x1": round(b.x1, 2),
                    "y1": round(b.y1, 2),
                    "x2": round(b.x2, 2),
                    "y2": round(b.y2, 2),
                    "score": round(b.score, 4),
                }
                for b in self.boxes
            ],
            "gaps": [g.to_dict() for g in self.gaps],
        }


def square_image(image: Image.Image, input_size: int = 640) -> np.ndarray:
    """Stretches an RGB image to (1, 3, S, S) float32 in the 0-1 range, as training did.

    Training resized every photo to a square without preserving aspect ratio, so inference
    must do the same: a letterboxed input would shift the geometry the detector learned.
    """
    rgb = image.convert("RGB").resize((input_size, input_size), Image.Resampling.BILINEAR)
    arr = np.asarray(rgb, dtype=np.float32) / 255.0
    chw = np.transpose(arr, (2, 0, 1))[np.newaxis, ...]
    return np.ascontiguousarray(chw)


def box_iou(a: Box, b: Box) -> float:
    """Computes Intersection-over-Union (IoU) between two boxes."""
    ix1 = max(a.x1, b.x1)
    iy1 = max(a.y1, b.y1)
    ix2 = min(a.x2, b.x2)
    iy2 = min(a.y2, b.y2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    union = a.width * a.height + b.width * b.height - inter
    return inter / union if union > 0.0 else 0.0


def apply_nms(boxes: Sequence[Box], iou_threshold: float = 0.45) -> list[Box]:
    """Suppresses overlapping detections sorted by descending confidence score."""
    ordered = sorted(boxes, key=lambda b: b.score, reverse=True)
    kept: list[Box] = []
    for candidate in ordered:
        if all(box_iou(candidate, existing) <= iou_threshold for existing in kept):
            kept.append(candidate)
    return kept


def decode_predictions(
    raw_output: np.ndarray,
    orig_width: int,
    orig_height: int,
    input_size: int = 640,
    score_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    max_dets: int = 1000,
) -> list[Box]:
    """Decodes FCOS candidates `(1, N, 6)` `[xc, yc, w, h, score, 1]` into original pixels."""
    preds = np.asarray(raw_output, dtype=np.float32)
    preds = preds.reshape(-1, preds.shape[-1])
    candidates: list[Box] = []
    sx = float(orig_width) / float(input_size)
    sy = float(orig_height) / float(input_size)

    for row in preds:
        if row.shape[0] < 5:
            continue
        xc, yc, w, h, score = (float(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4]))
        if score < score_threshold or w <= 1.0 or h <= 1.0:
            continue
        x1 = max(0.0, min(float(orig_width), (xc - w / 2.0) * sx))
        y1 = max(0.0, min(float(orig_height), (yc - h / 2.0) * sy))
        x2 = max(0.0, min(float(orig_width), (xc + w / 2.0) * sx))
        y2 = max(0.0, min(float(orig_height), (yc + h / 2.0) * sy))
        if x2 - x1 >= 2.0 and y2 - y1 >= 2.0:
            candidates.append(Box(x1=x1, y1=y1, x2=x2, y2=y2, score=score))

    return apply_nms(candidates, iou_threshold=iou_threshold)[:max_dets]


class ShelfDetector:
    """Runs shelf item detection using an ONNX Runtime session (or a deterministic fallback for testing)."""

    def __init__(
        self,
        model_path: Path | str | None = None,
        input_size: int = 640,
        score_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        allow_heuristic: bool | None = None,
    ) -> None:
        self.input_size = input_size
        self.score_threshold = score_threshold
        self.iou_threshold = iou_threshold
        self.session = None
        if model_path is not None and Path(model_path).is_file():
            import onnxruntime as ort

            self.session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        # Without a model the CLI/API fall back to a contrast heuristic that only works on clean
        # synthetic images and prints a warning. The browser never uses it, and no reported
        # number in this repository comes from it.
        self.allow_heuristic = (self.session is None) if allow_heuristic is None else allow_heuristic

    def detect_boxes(self, image: Image.Image) -> list[Box]:
        """Detects product boxes in a PIL image."""
        orig_w, orig_h = image.size
        tensor = square_image(image, input_size=self.input_size)

        if self.session is not None:
            input_name = self.session.get_inputs()[0].name
            outputs = self.session.run(None, {input_name: tensor})
            return decode_predictions(
                outputs[0],
                orig_width=orig_w,
                orig_height=orig_h,
                input_size=self.input_size,
                score_threshold=self.score_threshold,
                iou_threshold=self.iou_threshold,
            )

        if self.allow_heuristic:
            print(
                "warning: no ONNX model loaded, using the contrast heuristic, which only works on "
                "clean synthetic images. Counts from it are not model predictions.",
                file=sys.stderr,
            )
            return _detect_contrast_components(image)
        raise RuntimeError(
            "No ONNX detector is loaded. Pass --model path/to/shelfsense.onnx; "
            "the counted boxes must come from a real model."
        )

    def analyze(
        self,
        image: Image.Image,
        low_stock_threshold: int = 10,
        gap_multiplier: float = 1.35,
    ) -> ScanAnalysis:
        """Runs product detection, counts items, finds empty shelf gaps, and evaluates low-stock status."""
        orig_w, orig_h = image.size
        boxes = self.detect_boxes(image)
        gaps = detect_shelf_gaps(boxes, gap_multiplier=gap_multiplier)
        count = len(boxes)
        missing_total = sum(g.estimated_missing_items for g in gaps)
        return ScanAnalysis(
            image_width=orig_w,
            image_height=orig_h,
            count=count,
            low_stock=count < low_stock_threshold,
            low_stock_threshold=low_stock_threshold,
            boxes=tuple(boxes),
            gaps=tuple(gaps),
            estimated_missing_total=missing_total,
        )


def _detect_contrast_components(image: Image.Image) -> list[Box]:
    """Finds bright rectangular product regions against a darker shelf background when no ONNX file is loaded."""
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    h, w = gray.shape
    bg = float(np.percentile(gray, 25))
    mask = gray > (bg + 35.0)
    if not np.any(mask):
        return []

    visited = np.zeros_like(mask, dtype=bool)
    boxes: list[Box] = []

    # Step on a 2-pixel grid for speed, expanding connected foreground islands.
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            if mask[y, x] and not visited[y, x]:
                stack = [(y, x)]
                visited[y, x] = True
                min_x = max_x = x
                min_y = max_y = y
                while stack:
                    cy, cx = stack.pop()
                    if cx < min_x:
                        min_x = cx
                    if cx > max_x:
                        max_x = cx
                    if cy < min_y:
                        min_y = cy
                    if cy > max_y:
                        max_y = cy
                    for ny in (cy - 1, cy, cy + 1):
                        for nx in (cx - 1, cx, cx + 1):
                            if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not visited[ny, nx]:
                                visited[ny, nx] = True
                                stack.append((ny, nx))
                if (max_x - min_x) >= 6 and (max_y - min_y) >= 6:
                    boxes.append(Box(float(min_x), float(min_y), float(max_x + 1), float(max_y + 1), score=0.92))

    return apply_nms(boxes, iou_threshold=0.45)
