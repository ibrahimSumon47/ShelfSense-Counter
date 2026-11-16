// Shelf row clustering and empty-gap detection from detected product boxes.
// Groups products into horizontal shelf rows by vertical center proximity and
// flags empty horizontal spaces wider than `gapMultiplier * medianWidth`.

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  score: number;
}

export interface ShelfGap {
  rowIndex: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  width: number;
  estimatedMissingItems: number;
}

// Computes the statistical median of a non-empty numeric array.
export function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

// Groups product boxes into horizontal shelf rows ordered top-to-bottom, left-to-right.
export function clusterShelfRows(boxes: BoundingBox[], rowToleranceRatio = 0.65): BoundingBox[][] {
  if (boxes.length === 0) return [];
  const heights = boxes.map((b) => Math.max(0, b.y2 - b.y1)).filter((h) => h > 0);
  const medianH = heights.length > 0 ? median(heights) : 40;
  const maxDy = Math.max(8, medianH * rowToleranceRatio);

  const sortedByY = [...boxes].sort((a, b) => (a.y1 + a.y2) / 2 - (b.y1 + b.y2) / 2);
  const rows: BoundingBox[][] = [];
  const rowMeans: number[] = [];

  for (const box of sortedByY) {
    const cy = (box.y1 + box.y2) / 2;
    let placed = false;
    for (let i = 0; i < rowMeans.length; i++) {
      if (Math.abs(cy - rowMeans[i]) <= maxDy) {
        rows[i].push(box);
        rowMeans[i] = rows[i].reduce((acc, b) => acc + (b.y1 + b.y2) / 2, 0) / rows[i].length;
        placed = true;
        break;
      }
    }
    if (!placed) {
      rows.push([box]);
      rowMeans.push(cy);
    }
  }

  return rows
    .map((row, idx) => ({ meanY: rowMeans[idx], row: [...row].sort((a, b) => a.x1 - b.x1) }))
    .sort((a, b) => a.meanY - b.meanY)
    .map((item) => item.row);
}

// Detects empty horizontal gaps between adjacent items along each shelf row.
export function detectShelfGaps(
  boxes: BoundingBox[],
  gapMultiplier = 1.35,
  minRowItems = 2,
): ShelfGap[] {
  const rows = clusterShelfRows(boxes);
  const gaps: ShelfGap[] = [];

  rows.forEach((row, rowIndex) => {
    if (row.length < minRowItems) return;
    const widths = row.map((b) => b.x2 - b.x1).filter((w) => w > 1);
    if (widths.length === 0) return;
    const medianW = median(widths);
    const threshold = medianW * gapMultiplier;

    for (let i = 0; i < row.length - 1; i++) {
      const left = row[i];
      const right = row[i + 1];
      const spacing = right.x1 - left.x2;
      if (spacing >= threshold) {
        const missing = Math.max(1, Math.round(spacing / medianW));
        const x1 = Math.round(left.x2 * 100) / 100;
        const x2 = Math.round(right.x1 * 100) / 100;
        gaps.push({
          rowIndex,
          x1,
          y1: Math.round(Math.min(left.y1, right.y1) * 100) / 100,
          x2,
          y2: Math.round(Math.max(left.y2, right.y2) * 100) / 100,
          width: Math.round((x2 - x1) * 100) / 100,
          estimatedMissingItems: missing,
        });
      }
    }
  });

  return gaps;
}
