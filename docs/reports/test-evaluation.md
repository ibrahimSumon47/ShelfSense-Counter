# Test evaluation: FCOS ResNet-50 FPN, 12 epochs (run fcos-r50-fpn-v3)

The test split was scored once, with the threshold pair fixed on validation beforehand. Both
files below are the artifacts of the commands in this report; nothing was adjusted afterwards.

## Command

```
cd training
python eval_onnx.py \
  --onnx outputs/fcos-v3/outputs/fcos-r50-fpn-v3-fp32.onnx outputs/fcos-v3/outputs/fcos-r50-fpn-v3-int8.onnx \
  --dataset cc0 --split test --input-size 640 --normalise no --center-fix none \
  --score-thresh 0.30 --nms-thresh 0.35 --max-dets 1000 \
  --out ../docs/reports/test-evaluation.json --predictions-dir ../docs/reports/predictions
```

- ONNX files: `fcos-r50-fpn-v3-fp32.onnx` (SHA-256 `f303e0f7…3301`, 128.7 MB),
  `fcos-r50-fpn-v3-int8.onnx` (SHA-256 `e00176ae…` , 32.8 MB), both from Kaggle kernel
  `ibrahimhossainsumon/shelfsense-fcos-training` version 1, finished 2026-11-19 23:57.
- Checkpoint: `best.pt`, epoch 8 of 12 (SKU-110K validation mAP50 0.8602 under the training loop's
  own evaluator).
- Predictions are committed as `docs/reports/predictions/fcos-r50-fpn-v3-fp32-cc0-test.json.gz`
  and `docs/reports/predictions/fcos-r50-fpn-v3-int8-cc0-test.json.gz` (60 KiB each, boxes in
  original pixels), so every number here can be recomputed with pycocotools.

## Results (CC0 Supermarket Shelves test split, 9 images, 1,950 ground-truth items)

| Model | mAP50 | mAP50-95 | mAP75 | count MAE | count MAPE | detections | ms/image (CPU) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fp32 | 0.7227 | 0.3523 | 0.2846 | 26.56 | 20.68 % | 2,047 | 807 |
| int8 | 0.7215 | 0.3531 | 0.2854 | 25.67 | 19.91 % | 2,035 | 1,016 |

INT8 loses 0.0012 mAP50 and gains 0.9 items of count error, which is inside the spread between
neighbouring epochs, so the shipped browser model is the 32.8 MB int8 file.

Thresholds were tuned on the CC0 **validation** split (9 images) with
`--grid "0.15,0.2,0.25,0.3:0.35,0.45"`; best by count MAE was score 0.30 / NMS 0.35
(mAP50 0.5784, MAE 48.89 at maxDets 1000). Nine validation images give a wide interval: the 95 %
bootstrap interval on the fp32 test score is mAP50 0.5324-0.8196 and MAE 11.56-42.89, so treat
0.72 as "somewhere in the 0.5-0.8 band", not as a precise figure.

## What is not reported, and why

The run's own `metrics.json` contains SKU-110K validation and test numbers (mAP50 0.13,
MAE 563). They are **wrong and are not used anywhere**: `train.py` evaluated the exported graph
with `run_raw_candidates(..., normalise=True)`, while the exporter bakes ImageNet mean/std into
the graph, so the network was normalised twice and produced about 700 detections per image. The
same checkpoint scores 0.5976 on CC0 validation through the corrected path, which is consistent
with the training loop's own 0.54-0.60, so the weights and the export are fine and the evaluator
was not. `onnx_eval.run_raw_candidates` now defaults to `normalise=False`,
`training/tests/test_onnx_normalisation_default.py` pins that default, and both call sites in
`train.py` pass the flag explicitly.

Consequently there is no SKU-110K test number in this report: the local machine holds only the 45
CC0 images, and re-scoring 200 SKU-110K test images needs a fresh Kaggle run with the fixed
evaluator. The CC0 split is a different store and density profile from SKU-110K, so its 0.72 does
not transfer to dense shelf photos. Until that run exists, the honest statement about dense SKU
images is "not measured on test", not a number.

## Failure shape

The errors that matter are over-counts on medium shelves, not misses on dense ones. Overall the
fp32 file finds 2,047 boxes for 1,950 items, but the spread is uneven:

| image | ground truth | predicted | error |
| --- | --- | --- | --- |
| `005.jpg` | 251 | 335 | +84 (+33 %) |
| `040.jpg` | 71 | 111 | +40 (+56 %) |
| `002.jpg` | 690 | 657 | -33 (-5 %) |

By density, fp32 scores mAP50 0.654 on the four medium images (50-150 items) and 0.741 on the five
dense ones (over 150), with count MAE 20.5 and 31.4 respectively; int8 is 0.640 and 0.734. The
largest shelf in the split (`002.jpg`, 690 items) is counted to within 5 %, so the failure mode is
splitting a product into two boxes on the mid-density photos, where a shelf gap or a price rail
creates a seam the box regressor treats as two items.

## Published weights and the live app

Release `v1.0.0` carries `fcos-r50-fpn-v3-fp32.onnx`, `fcos-r50-fpn-v3-int8.onnx`,
`shelfsense-regression-v1.tar.gz` (20 fixed images with their counts and mAP) and
`sha256sums.txt`. The web app loads the int8 file from
`https://shelfsense-counter.vercel.app/models/shelfsense-v3-int8.onnx` (32,818,871 bytes,
`application/octet-stream`, HTTP 200) and its `/models/manifest.json` reports the same SHA-256.

On the live site, uploading `002.jpg` (690 ground-truth items) produced **663 products in 3,996 ms**
on WASM with the int8 model, against 657 from the Python fp32 path on the same image; the 6-item
difference is INT8 plus the browser's 640 px square stretch. That is a real measurement in the
deployed page, not a local build.
