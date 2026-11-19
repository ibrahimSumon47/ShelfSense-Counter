// In-browser ONNX Runtime Web shelf detector and image preprocessing helpers.
// Resizes photos on the client before inference or thumbnail upload so raw photos
// stay on the user's device and never hit Vercel's 4.5 MB function payload limit.
//
// The detector is a torchvision FCOS ResNet-50 FPN exported to ONNX. The graph normalises
// its input and decodes anchors itself, and returns dense candidates
// `[1, N, 6] = [xc, yc, w, h, score, 1]` in input-pixel coordinates. Thresholding, NMS and
// the cap on detections happen here, in the same order as `training/eval_onnx.py`, so the
// browser count and the Python count on the same photo agree.

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

export interface DetectorParams {
  inputSize: number;
  scoreThreshold: number;
  nmsThreshold: number;
  maxDets: number;
}

// How a particular ONNX file expects its input. The current exporter bakes the ImageNet
// normalisation and the anchor centres into the graph; the first two exports did not, so the
// manifest can say so and this file corrects for it. Both flags describe the file, not the app.
export interface FcosPreprocessing {
  normaliseInGraph: boolean;
  centreOffsetFix: boolean;
}

export const MODERN_PREPROCESSING: FcosPreprocessing = { normaliseInGraph: true, centreOffsetFix: false };

const IMAGENET_MEAN = [0.485, 0.456, 0.406];
const IMAGENET_STD = [0.229, 0.224, 0.225];

// Feature-pyramid level sizes and strides for a square input, used by the legacy centre fix.
export function fcosLevels(inputSize: number): Array<{ count: number; stride: number }> {
  return [8, 16, 32, 64, 128].map((stride) => {
    const cells = inputSize / stride;
    if (!Number.isInteger(cells)) {
      throw new Error(`input size ${inputSize} is not a multiple of the stride ${stride}`);
    }
    return { count: cells * cells, stride };
  });
}

// Shifts every candidate centre back by half a cell, level by level.
// The first exports decoded centres at (g + 0.5) * stride while torchvision's AnchorGenerator
// uses g * stride, so every box sat half a cell down and right.
export function legacyCentreFixedCandidates(
  raw: ArrayLike<number>,
  numCandidates: number,
  inputSize: number,
): Float32Array {
  const fixed = Float32Array.from(raw as ArrayLike<number>).slice(0, numCandidates * 6);
  let offset = 0;
  for (const level of fcosLevels(inputSize)) {
    for (let i = 0; i < level.count && offset + i < numCandidates; i++) {
      fixed[(offset + i) * 6] -= 0.5 * level.stride;
      fixed[(offset + i) * 6 + 1] -= 0.5 * level.stride;
    }
    offset += level.count;
  }
  return fixed;
}

// Defaults are the values tuned on the 200-image SKU-110K validation split.
export const DEFAULT_DETECTOR_PARAMS: DetectorParams = {
  inputSize: 640,
  scoreThreshold: 0.3,
  nmsThreshold: 0.35,
  maxDets: 1000,
};

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

// Turns the FCOS candidate tensor into boxes in the original photo's pixels.
// `raw` is the flattened `[N, 6]` output: centre x, centre y, width, height, score, 1.
export function decodeFcosCandidates(
  raw: ArrayLike<number>,
  numCandidates: number,
  inputSize: number,
  origWidth: number,
  origHeight: number,
  params: DetectorParams = DEFAULT_DETECTOR_PARAMS,
): BoundingBox[] {
  if (inputSize <= 0 || origWidth <= 0 || origHeight <= 0) {
    throw new Error('decodeFcosCandidates needs positive input and image sizes');
  }
  const candidates: BoundingBox[] = [];
  for (let i = 0; i < numCandidates; i++) {
    const offset = i * 6;
    const xc = raw[offset];
    const yc = raw[offset + 1];
    const w = raw[offset + 2];
    const h = raw[offset + 3];
    const score = raw[offset + 4];
    if (score < params.scoreThreshold || w <= 1 || h <= 1) continue;
    // Candidates are in input pixels; stretch both axes back to the photo's own size,
    // which is the same mapping training and the Python CLI use.
    const sx = origWidth / inputSize;
    const sy = origHeight / inputSize;
    const x1 = Math.max(0, Math.min(origWidth, (xc - w / 2) * sx));
    const y1 = Math.max(0, Math.min(origHeight, (yc - h / 2) * sy));
    const x2 = Math.max(0, Math.min(origWidth, (xc + w / 2) * sx));
    const y2 = Math.max(0, Math.min(origHeight, (yc + h / 2) * sy));
    if (x2 - x1 < 2 || y2 - y1 < 2) continue;
    candidates.push({
      x1: Math.round(x1 * 100) / 100,
      y1: Math.round(y1 * 100) / 100,
      x2: Math.round(x2 * 100) / 100,
      y2: Math.round(y2 * 100) / 100,
      score: Math.round(score * 10000) / 10000,
    });
  }
  return applyNms(candidates, params.nmsThreshold).slice(0, params.maxDets);
}

// Converts an RGBA buffer that is already `inputSize x inputSize` into a float32 CHW tensor
// in the 0-1 range. Resizing happens on the canvas (bilinear, stretched to a square) because
// the detector was fine-tuned on stretched squares, not on letterboxed padding.
export function rgbaToChw(
  rgba: Uint8ClampedArray | Uint8Array,
  inputSize: number,
  preprocessing: FcosPreprocessing = MODERN_PREPROCESSING,
): Float32Array {
  const plane = inputSize * inputSize;
  if (rgba.length < plane * 4) {
    throw new Error(`rgbaToChw expected ${plane * 4} bytes, received ${rgba.length}`);
  }
  const tensor = new Float32Array(3 * plane);
  for (let c = 0; c < 3; c++) {
    const mean = IMAGENET_MEAN[c];
    const std = IMAGENET_STD[c];
    for (let i = 0; i < plane; i++) {
      const value = rgba[i * 4 + c] / 255;
      // Files that do not normalise internally need the same mean/std torchvision applied in training.
      tensor[c * plane + i] = preprocessing.normaliseInGraph ? value : (value - mean) / std;
    }
  }
  return tensor;
}

// Loads the ONNX file with WebGPU when the browser supports it and the file can run there,
// otherwise on WASM. The dynamically quantised INT8 graph measured on this machine returned
// the detection cap (1000 boxes) for a 690-item shelf under WebGPU while WASM found 482, so
// quantised files declare `webgpu_capable: false` in the manifest and go straight to WASM.
export async function loadOnnxDetector(
  modelUrl: string,
  allowWebGpu = true,
): Promise<{ session: unknown; provider: 'webgpu' | 'wasm' }> {
  const ort = await import('onnxruntime-web');
  const webgpuAvailable =
    allowWebGpu &&
    typeof navigator !== 'undefined' &&
    'gpu' in navigator &&
    Boolean((navigator as { gpu?: unknown }).gpu);
  const attempts: Array<'webgpu' | 'wasm'> = webgpuAvailable ? ['webgpu', 'wasm'] : ['wasm'];
  let lastError: unknown = null;
  for (const provider of attempts) {
    try {
      const session = await ort.InferenceSession.create(modelUrl, {
        executionProviders: [provider],
        graphOptimizationLevel: 'all',
      });
      return { session, provider };
    } catch (error) {
      lastError = error;
    }
  }
  throw new Error(`Could not create an ONNX session: ${String(lastError)}`);
}

// Runs one photo through the detector and returns boxes in the photo's pixels plus timing.
export async function runFcosDetection(
  session: { run: (feeds: Record<string, unknown>) => Promise<Record<string, { data: Float32Array }>>; inputNames: readonly string[] },
  provider: 'webgpu' | 'wasm',
  rgba: Uint8ClampedArray | Uint8Array,
  origWidth: number,
  origHeight: number,
  params: DetectorParams = DEFAULT_DETECTOR_PARAMS,
  preprocessing: FcosPreprocessing = MODERN_PREPROCESSING,
): Promise<{ boxes: BoundingBox[]; inferenceMs: number; executionProvider: 'webgpu' | 'wasm' }> {
  // Lazy import keeps the node test runner from loading the runtime at all.
  const ort = await import('onnxruntime-web');
  const tensorData = rgbaToChw(rgba, params.inputSize, preprocessing);
  const input = new ort.Tensor('float32', tensorData, [1, 3, params.inputSize, params.inputSize]);
  const started = typeof performance !== 'undefined' ? performance.now() : Date.now();
  const outputs = await session.run({ [session.inputNames[0]]: input });
  const inferenceMs = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - started;
  const output = outputs[session.inputNames[0]] ?? Object.values(outputs)[0];
  const numCandidates = Math.floor(output.data.length / 6);
  const fixed = preprocessing.centreOffsetFix
    ? legacyCentreFixedCandidates(output.data, numCandidates, params.inputSize)
    : output.data;
  const boxes = decodeFcosCandidates(fixed, numCandidates, params.inputSize, origWidth, origHeight, params);
  return { boxes, inferenceMs, executionProvider: provider };
}

// Builds a complete DetectionResult from detected boxes, threshold, and timing.
export function buildDetectionResult(
  boxes: BoundingBox[],
  imageWidth: number,
  imageHeight: number,
  lowStockThreshold: number,
  inferenceMs = 0,
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
