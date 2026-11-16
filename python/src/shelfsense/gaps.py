"""Shelf row clustering and empty-gap detection from product bounding boxes.

Groups detected items into horizontal shelf rows by vertical center proximity,
computes the median item width per row, and flags empty horizontal gaps between
adjacent items (or shelf margins) that exceed `gap_multiplier * median_width`.
"""
from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from typing import Sequence


@dataclass(frozen=True)
class Box:
    """Detected product bounding box in pixel coordinates."""

    x1: float
    y1: float
    x2: float
    y2: float
    score: float = 1.0

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def center_y(self) -> float:
        return (self.y1 + self.y2) / 2.0


@dataclass(frozen=True)
class ShelfGap:
    """An empty horizontal space along a shelf row where stock is missing."""

    row_index: int
    x1: float
    y1: float
    x2: float
    y2: float
    estimated_missing_items: int

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["width"] = round(self.width, 2)
        return data


def cluster_shelf_rows(boxes: Sequence[Box], row_tolerance_ratio: float = 0.65) -> list[list[Box]]:
    """Groups product boxes into horizontal shelf rows ordered top-to-bottom, left-to-right."""
    if not boxes:
        return []

    median_h = statistics.median(b.height for b in boxes if b.height > 0) if any(b.height > 0 for b in boxes) else 40.0
    max_dy = max(8.0, median_h * row_tolerance_ratio)

    sorted_by_y = sorted(boxes, key=lambda b: b.center_y)
    rows: list[list[Box]] = []
    row_means: list[float] = []

    for box in sorted_by_y:
        placed = False
        for idx, mean_y in enumerate(row_means):
            if abs(box.center_y - mean_y) <= max_dy:
                rows[idx].append(box)
                row_means[idx] = sum(b.center_y for b in rows[idx]) / len(rows[idx])
                placed = True
                break
        if not placed:
            rows.append([box])
            row_means.append(box.center_y)

    # Order rows top-to-bottom and items within each row left-to-right.
    paired = sorted(zip(row_means, rows), key=lambda pair: pair[0])
    return [sorted(r, key=lambda b: b.x1) for _, r in paired]


def detect_shelf_gaps(
    boxes: Sequence[Box],
    gap_multiplier: float = 1.35,
    min_row_items: int = 2,
) -> list[ShelfGap]:
    """Finds empty gaps between adjacent products along each detected shelf row."""
    rows = cluster_shelf_rows(boxes)
    gaps: list[ShelfGap] = []

    for row_idx, row in enumerate(rows):
        if len(row) < min_row_items:
            continue
        widths = [b.width for b in row if b.width > 1.0]
        if not widths:
            continue
        median_w = statistics.median(widths)
        threshold = median_w * gap_multiplier

        for i in range(len(row) - 1):
            left = row[i]
            right = row[i + 1]
            spacing = right.x1 - left.x2
            if spacing >= threshold:
                missing = max(1, round(spacing / median_w))
                y1 = min(left.y1, right.y1)
                y2 = max(left.y2, right.y2)
                gaps.append(
                    ShelfGap(
                        row_index=row_idx,
                        x1=round(left.x2, 2),
                        y1=round(y1, 2),
                        x2=round(right.x1, 2),
                        y2=round(y2, 2),
                        estimated_missing_items=missing,
                    )
                )

    return gaps
