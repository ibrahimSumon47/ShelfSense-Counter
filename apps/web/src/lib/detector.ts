// In-browser ONNX Runtime Web shelf detector and image preprocessing helpers.
// Resizes photos on the client before inference or thumbnail upload so raw photos
// stay on the user's device and never hit Vercel's 4.5 MB function payload limit.

import { type BoundingBox, type ShelfGap, detectShelfGaps } from './gaps.ts';

export interface DetectionResult {
  imageWidth: number;
  imageHeight: number;
  count: number;
  lowStock: boolean;
  lowStockThreshold: number;
  estimatedMissingTotal: number;
  boxes: BoundingBox[];
  gaps: ShelfGap[];
  inferenceMs: number;
  executionProvider: 'webgpu' | 'wasm' | 'canvas-fallback';
}

// Computes target dimensions that fit within `maxEdge` while preserving aspect ratio.
export function computeResizedDimensions(
  width: number,
  height: number,
  maxEdge = 1280,
): { width: number; height: number; scale: number } {
  if (width <= 0 || height <= 0) {
    throw new Error(`Invalid image dimensions: ${width}x${height}`);
  }
  const largest = Math.max(width, height);
  if (largest <= maxEdge) {
    return { width, height, scale: 1 };
  }
  const scale = maxEdge / largest;
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
    scale,
  };
}

// Computes Intersection-over-Union (IoU) between two bounding boxes.
export function boxIou(a: BoundingBox, b: BoundingBox): number {
  const ix1 = Math.max(a.x1, b.x1);
  const iy1 = Math.max(a.y1, b.y1);
  const ix2 = Math.min(a.x2, b.x2);
  const iy2 = Math.min(a.y2, b.y2);
  const iw = Math.max(0, ix2 - ix1);
  const ih = Math.max(0, iy2 - iy1);
  const inter = iw * ih;
  if (inter <= 0) return 0;
  const areaA = Math.max(0, a.x2 - a.x1) * Math.max(0, a.y2 - a.y1);
  const areaB = Math.max(0, b.x2 - b.x1) * Math.max(0, b.y2 - b.y1);
  const union = areaA + areaB - inter;
  return union > 0 ? inter / union : 0;
}

// Suppresses overlapping boxes sorted by descending confidence score.
export function applyNms(boxes: BoundingBox[], iouThreshold = 0.45): BoundingBox[] {
  const ordered = [...boxes].sort((a, b) => b.score - a.score);
  const kept: BoundingBox[] = [];
  for (const candidate of ordered) {
    if (kept.every((existing) => boxIou(candidate, existing) <= iouThreshold)) {
      kept.push(candidate);
    }
  }
  return kept;
}

// Decodes a flat YOLOX output tensor `[xc, yc, w, h, obj_conf, cls_conf]` per anchor
// back to original pixel coordinates and applies Non-Maximum Suppression.
export function decodeYoloxOutput(
  data: Float32Array | number[],
  numAnchors: number,
  strideCols: number,
  origWidth: number,
  origHeight: number,
  scale: number,
  padX: number,
  padY: number,
  scoreThreshold = 0.25,
  iouThreshold = 0.45,
): BoundingBox[] {
  const candidates: BoundingBox[] = [];
  for (let i = 0; i < numAnchors; i++) {
    const offset = i * strideCols;
    const xc = data[offset];
    const yc = data[offset + 1];
    const w = data[offset + 2];
    const h = data[offset + 3];
    const obj = data[offset + 4];
    const cls = strideCols > 5 ? data[offset + 5] : 1;
    const score = obj * cls;

    if (score < scoreThreshold || w <= 1 || h <= 1) continue;

    const x1 = Math.max(0, Math.min(origWidth, (xc - w / 2 - padX) / scale));
    const y1 = Math.max(0, Math.min(origHeight, (yc - h / 2 - padY) / scale));
    const x2 = Math.max(0, Math.min(origWidth, (xc + w / 2 - padX) / scale));
    const y2 = Math.max(0, Math.min(origHeight, (yc + h / 2 - padY) / scale));

    if (x2 - x1 >= 2 && y2 - y1 >= 2) {
      candidates.push({
        x1: Math.round(x1 * 100) / 100,
        y1: Math.round(y1 * 100) / 100,
        x2: Math.round(x2 * 100) / 100,
        y2: Math.round(y2 * 100) / 100,
        score: Math.round(score * 10000) / 10000,
      });
    }
  }
  return applyNms(candidates, iouThreshold);
}

// Builds a complete DetectionResult from detected boxes, threshold, and timing.
export function buildDetectionResult(
  boxes: BoundingBox[],
  imageWidth: number,
  imageHeight: number,
  lowStockThreshold: number,
  inferenceMs = 12,
  executionProvider: DetectionResult['executionProvider'] = 'wasm',
): DetectionResult {
  const gaps = detectShelfGaps(boxes);
  const count = boxes.length;
  const estimatedMissingTotal = gaps.reduce((sum, g) => sum + g.estimatedMissingItems, 0);
  return {
    imageWidth,
    imageHeight,
    count,
    lowStock: count < lowStockThreshold,
    lowStockThreshold,
    estimatedMissingTotal,
    boxes,
    gaps,
    inferenceMs: Math.round(inferenceMs),
    executionProvider,
  };
}
