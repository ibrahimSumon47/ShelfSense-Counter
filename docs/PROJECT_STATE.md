# Project state

Last updated: 2026-11-19 (FCOS pipeline: detection cap measured, export geometry fixed, GPU run pushed)

## Detector

`torchvision.models.detection.fcos_resnet50_fpn`, BSD-3-Clause, 32,064,455 parameters,
COCO-pretrained, fine-tuned for one class (`item`), 640 px input. The official YOLOX install
failed twice inside the Kaggle image, so the detector name and every kernel, notebook and ADR
now say FCOS; the new kernel is `ibrahimhossainsumon/shelfsense-fcos-training`.

## Measured now (validation only)

| Split | Model file | maxDets | mAP50 | mAP50-95 | count MAE | count MAPE |
| --- | --- | --- | --- | --- | --- | --- |
| CC0 val (9 images, 1922 items) | improved v2 fp32 | 1000 | 0.5306 | 0.2816 | 72.67 | 68.43 % |
| CC0 val | improved v2 int8 | 1000 | 0.5309 | 0.2798 | 74.00 | 69.35 % |
| CC0 val | baseline v1 fp32 | 1000 | 0.5010 | 0.2331 | 141.89 | 109.09 % |
| CC0 val | improved v2 fp32 | 100 | 0.3006 | 0.1813 | 132.44 | 80.32 % |

Command, per-image tables, bootstrap intervals and the 2×2 export-defect experiment:
`docs/reports/validation-detection-cap.md`, machine-readable in
`docs/reports/validation-cap-cc0-val.json` and `docs/reports/validation-sweep-cc0-val.json`,
with the prediction boxes committed under `docs/reports/predictions/`.

Two defects found and fixed in the ONNX export: the graph skipped the ImageNet normalisation,
and it decoded anchor centres at `(g + 0.5) * stride` instead of torchvision's `g * stride`.
Together they cost about 0.15 mAP50 on validation.

## Pipeline

- `training/train.py`: one resumable run, AMP, checkpoint every epoch and a separate `best.pt`
  before any export or evaluation, epoch count planned from images/s measured on the first 50
  batches against a 3-hour GPU budget, thresholds tuned on the 200-image SKU-110K validation
  split, test evaluated once.
- Export, evaluation and metrics writing each run in their own try/except and leave a
  `<block>-error.txt`, so a late failure never loses the training.
- `training/eval_onnx.py`: re-evaluates any ONNX file on a split with `pycocotools`
  (`maxDets` 100 vs 1000 side by side), a threshold grid, bootstrap intervals and density
  buckets, and writes gzipped prediction files.
- CI exports a tiny randomly initialised FCOS to ONNX on CPU at 128 px before any GPU run.

## In-browser detection (development stand-in)

`apps/web` loads `/models/<file>` named by `apps/web/public/models/manifest.json` with
`onnxruntime-web` 1.31.1, decodes FCOS candidates in `detector.ts` and draws the boxes over the
photo. Measured on the first two-epoch INT8 file (`docs/reports/browser-detection.md`):

| Photo | Ground truth | Python | Browser | Inference |
| --- | --- | --- | --- | --- |
| 002.jpg | 690 | 482 | 481 | 2982 ms |
| 005.jpg | 251 | 388 | 387 | 3466 ms |
| 006.jpg | 59 | 161 | 170 | 2985 ms |
| non-shelf.jpg | 0 | 12 | 12 | 2727 ms |

Two runtime defects were found and are fixed: `onnxruntime-web` 1.20 executed the INT8 graph
wrongly (12 boxes where Python found 482; 1.31.1 gives 481), and WebGPU returns the detection cap
(1000 boxes) for quantised weights, so INT8 files declare `webgpu_capable: false` and run on WASM.
FP32 on WebGPU is correct (504 for the same photo, 4845 ms).

## What is still open

- The 6000-image, 12-epoch run (`shelfsense-fcos-training`) is pushed and queued. Its
  validation numbers replace the two-epoch table above; the test split is then evaluated once
  and the weights published.
- Publish the released weights into `apps/web/public/models/`, deploy, and repeat the browser
  measurement on production (`S4-05`, `S2-06`).
- The GitHub release (`S2-07`), the test report (`S3-01`, `S3-02`), production
  Playwright/axe/Lighthouse (`S7-01`, `S7-02`) and the closing README pass (`S8-01`).
