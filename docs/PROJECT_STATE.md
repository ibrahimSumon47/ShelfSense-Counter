# Project state

Last updated: 2026-11-20 (SKU-110K validation and test measured with the corrected evaluator;
release published, site deployed, model card and README written against the numbers)

## Detector

`torchvision.models.detection.fcos_resnet50_fpn`, BSD-3-Clause, 32,064,455 parameters,
COCO-pretrained, fine-tuned for one class (`item`), 640 px input. The official YOLOX install
failed twice inside the Kaggle image, so the detector name and every kernel, notebook and ADR
now say FCOS; the training kernel is `ibrahimhossainsumon/shelfsense-fcos-training` version 1.

## Measured now (run fcos-r50-fpn-v3, 12 epochs, best checkpoint from epoch 8)

Thresholds were fixed on SKU-110K validation by count MAE (score 0.30, NMS 0.35, maxDets 1000)
before any test image was scored.

| Split | Model file | mAP50 | mAP50-95 | count MAE | count MAPE |
| --- | --- | --- | --- | --- | --- |
| SKU-110K test (200 images, 29,092 items) | int8 | 0.8418 | 0.4844 | 26.52 | 21.29 % |
| SKU-110K test | fp32 | 0.8418 | 0.4851 | 26.55 | 21.30 % |
| SKU-110K val (200 images, 30,119 items) | int8 | 0.8524 | 0.5009 | 27.68 | 21.00 % |
| SKU-110K val | fp32 | 0.8602 | 0.5016 | 27.68 | 20.99 % |
| CC0 test (9 images, 1,950 items) | int8 | 0.7215 | 0.3531 | 25.67 | 19.91 % |
| CC0 test | fp32 | 0.7227 | 0.3523 | 26.56 | 20.68 % |

Command, per-image tables, bootstrap intervals, density buckets and the rescoring recipe:
`docs/reports/test-evaluation.md`, machine-readable in `docs/reports/sku110k-val.json`,
`docs/reports/sku110k-test.json`, `docs/reports/sku110k-summary.json` and
`docs/reports/test-evaluation.json`, with the prediction boxes committed under
`docs/reports/predictions/`. The two-epoch run's CC0 validation numbers are kept for history in
`docs/reports/validation-detection-cap.md`.

Three defects were found and fixed, each costing real accuracy or real numbers:

- the ONNX graph skipped the ImageNet normalisation and decoded anchor centres at
  `(g + 0.5) * stride` instead of torchvision's `g * stride` (about 0.15 mAP50 on validation);
- `train.py` then normalised the input a second time on top of the fixed graph, which turned the
  run's own SKU-110K numbers into mAP50 0.13 garbage; `run_raw_candidates` now defaults to
  `normalise=False` and a test pins it;
- the eval notebook's summary cell read `onnx_file` from `primary`, where it does not exist, so it
  died with `KeyError` after both splits had already been scored; the cell is fixed.

## Pipeline

- `training/train.py`: one resumable run, AMP, checkpoint every epoch and a separate `best.pt`
  before any export or evaluation, epoch count planned from images/s measured on the first 50
  batches against a 3-hour GPU budget, thresholds tuned on the 200-image SKU-110K validation
  split, test evaluated once. The 12-epoch run took 12,658 s (4.39 images/s) because
  `plan_epochs()` clamps to `min_epochs`.
- Export, evaluation and metrics writing each run in their own try/except and leave a
  `<block>-error.txt`, so a late failure never loses the training.
- `training/eval_onnx.py`: re-evaluates any ONNX file on a split with `pycocotools`
  (`maxDets` 100 vs 1000 side by side), a threshold grid, bootstrap intervals and density
  buckets, and writes gzipped prediction files.
- CI exports a tiny randomly initialised FCOS to ONNX on CPU at 128 px before any GPU run, and
  scores the 20-image regression bundle when release `v1.0.0` exists.

## In-browser detection (production)

`apps/web` loads `/models/<file>` named by `apps/web/public/models/manifest.json` with
`onnxruntime-web` 1.31.1, decodes FCOS candidates in `detector.ts` and draws the boxes over the
photo. The deployed site runs the 32.8 MB INT8 graph on WASM: `002.jpg` (690 items) reported 663
products in 3,996 ms, against 657 from the Python fp32 path on the same image. Three runtime
defects were found and are fixed: `onnxruntime-web` 1.20 executed the INT8 graph wrongly (12 boxes
where Python found 482; 1.31.1 gives 481), WebGPU returns the detection cap for quantised weights,
so INT8 declares `webgpu_capable: false`, and the manifest now carries the production file with
its SHA-256. Earlier development measurements are in `docs/reports/browser-detection.md`.

## What is still open

- `S7-01` Playwright flows against the production URL, and `S7-02` axe-core and Lighthouse
  scores recorded on production.
- The live-LLM chat checks cannot be re-run on this PC because `private/.env.local` is missing and
  the key cannot be read back from Vercel; the owner steps are item 2b in `docs/OWNER_TODO.md`.
  The `S5-03` figures come from the run made with the key still available.
