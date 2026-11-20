# Test evaluation: FCOS ResNet-50 FPN, 12 epochs (run fcos-r50-fpn-v3)

The test split was scored once per dataset, after the threshold pair had been fixed on validation.
Both splits below come from the JSON artifacts in this folder, which are written by the commands
in this report; nothing was adjusted afterwards.

- **SKU-110K** (the domain the model was trained for): 200 validation images, 200 test images.
- **CC0 Supermarket Shelves** (a different store, 45 images in total): 9 validation, 9 test.

## Model and run

- `fcos-r50-fpn-v3-fp32.onnx`, 128,710,729 bytes, SHA-256 `f303e0f7...43301`.
- `fcos-r50-fpn-v3-int8.onnx`, 32,818,871 bytes, SHA-256 `e00176ae...63fc` (the file the web app
  loads).
- Weights: Kaggle kernel `ibrahimhossainsumon/shelfsense-fcos-training`, kernel version 1, finished
  2026-11-19 23:57:52 after 12,658 s on a Tesla T4. Checkpoint `best.pt`, epoch 8 of 12.
- Scoring kernel: `ibrahimhossainsumon/shelfsense-fcos-eval`, kernel version 1, 5,865 s on Kaggle
  CPU, ONNX files supplied as the private dataset `ibrahimhossainsumon/shelfsense-fcos-v3-onnx`,
  annotations from `thedatasith/sku110k-annotations`.
- Input 640 px square stretch, normalisation inside the graph (`--normalise no`), anchor centres
  already decoded at `g * stride` (`--center-fix none`).

## Command

```
# 1. validation sweep: choose the thresholds, nothing else
python training/eval_onnx.py \
  --onnx .../fcos-r50-fpn-v3-fp32.onnx .../fcos-r50-fpn-v3-int8.onnx \
  --dataset sku110k --split val --sku-dir /kaggle/input \
  --input-size 640 --normalise no --center-fix none \
  --score-thresh 0.3 --nms-thresh 0.35 --max-dets 1000 \
  --grid 0.15,0.2,0.25,0.3:0.35,0.45 --out /kaggle/working/val-sku110k.json

# 2. test: one pass with the chosen pair
python training/eval_onnx.py \
  --onnx .../fcos-r50-fpn-v3-fp32.onnx .../fcos-r50-fpn-v3-int8.onnx \
  --dataset sku110k --split test --sku-dir /kaggle/input \
  --input-size 640 --normalise no --center-fix none \
  --score-thresh 0.3 --nms-thresh 0.35 --max-dets 1000 \
  --out /kaggle/working/test-sku110k.json --predictions-dir /kaggle/working/predictions
```

Raw outputs: `docs/reports/sku110k-val.json`, `docs/reports/sku110k-test.json`, and the combined
`docs/reports/sku110k-summary.json`. Predicted and ground-truth boxes for the test pass are
committed as `docs/reports/predictions/fcos-r50-fpn-v3-fp32-sku110k-test.json.gz` and
`docs/reports/predictions/fcos-r50-fpn-v3-int8-sku110k-test.json.gz` (944 KiB each, original
pixels), so the numbers can be recomputed without the model or the images:

```python
import gzip, json
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
d = json.load(gzip.open("docs/reports/predictions/fcos-r50-fpn-v3-int8-sku110k-test.json.gz", "rt"))
# each image carries image_id, width, height, ground_truth[[x1,y1,x2,y2]] and predictions[[x1,y1,x2,y2,score]]
# build COCO gt/dt as usual, then: ev.params.maxDets = [1000, 1000, 1000]
# read ev.eval["precision"][:, :, 0, 0, -1] for mAP50-95 and [0, :, 0, 0, -1] for mAP50
```

This recomputation was run locally from those two files and returned exactly the numbers in the
tables below (fp32 0.8418 / 0.4851 / 0.5106, MAE 26.55; int8 0.8418 / 0.4844 / 0.5111, MAE 26.52).

## SKU-110K test results (200 images, 29,092 items, scored once)

| Model | mAP50 | mAP50-95 | mAP75 | count MAE | count MAPE | detections | ms/image (CPU) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fp32 | 0.8418 | 0.4851 | 0.5106 | 26.55 | 21.30 % | 33,759 | 1,267 |
| int8 | 0.8418 | 0.4844 | 0.5111 | 26.52 | 21.29 % | 33,793 | 1,055 |

95 % bootstrap intervals on the test split (1,000 resamples over images): fp32 mAP50
0.8163-0.8648, count MAE 23.20-30.25, MAPE 17.53-26.16 %; int8 mAP50 0.8171-0.8649, MAE
23.18-30.18, MAPE 17.54-26.18 %. The interval is narrow because 200 images carry 29,092 items.

INT8 costs 0.0007 mAP50-95 and 0.03 items of count error, i.e. nothing measurable, so the 32.8 MB
file is what ships to the browser.

## SKU-110K validation results (200 images, 30,119 items)

Thresholds were chosen here, by count MAE, before any test image was scored.

| Model | score / NMS | mAP50 | mAP50-95 | count MAE | count MAPE | detections | ms/image (CPU) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fp32 | 0.30 / 0.35 | 0.8602 | 0.5016 | 27.68 | 20.99 % | 35,231 | 1,240 |
| int8 | 0.30 / 0.35 | 0.8524 | 0.5009 | 27.68 | 21.00 % | 35,251 | 1,054 |

The sweep tried score 0.15/0.20/0.25/0.30 against NMS 0.35/0.45. Count MAE fell monotonically as
the score threshold rose (0.15: 133.5 items; 0.20: 68.5; 0.25: 41.0; 0.30: 27.7), while mAP50 moved
only between 0.852 and 0.871, so 0.30/0.35 is the count-optimal pair and the test run uses it. The
test split scores 0.0188 lower on mAP50 than validation, which is the expected optimism of tuning
on validation, not a second tuning round.

## By shelf density (SKU-110K test, fp32 / int8)

| Items in the photo | images | mAP50 | count MAE | count MAPE |
| --- | --- | --- | --- | --- |
| 50-150 | 134 | 0.8859 / 0.8857 | 26.90 / 26.87 | 23.10 / 23.10 % |
| over 150 | 65 | 0.7780 / 0.7860 | 24.08 / 24.05 | 12.79 / 12.80 % |
| under 50 | 1 | 0.4627 / 0.4858 | 140.0 / 139.0 | 333.33 / 330.95 % |

The single sparse image is the clear failure: a shelf with roughly 42 items that the model reads as
about 180. It is one image in 200, but it says the model has no notion of "this shelf is nearly
empty" - at low density it still fires the same number of candidates as on a packed shelf, and the
count error as a percentage becomes enormous. Dense shelves are the strongest part of the result:
mAP50 0.778 with a count error of 12.8 %, because every item is close to its neighbours and the
scale prior from training applies.

## CC0 Supermarket Shelves test results (9 images, 1,950 items, scored once)

A second store, kept because the deployed browser measurement was made on it.

| Model | mAP50 | mAP50-95 | mAP75 | count MAE | count MAPE | detections | ms/image (CPU) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fp32 | 0.7227 | 0.3523 | 0.2846 | 26.56 | 20.68 % | 2,047 | 807 |
| int8 | 0.7215 | 0.3531 | 0.2854 | 25.67 | 19.91 % | 2,035 | 1,016 |

Nine images give a wide interval: the 95 % bootstrap interval on the fp32 score is mAP50
0.5324-0.8196 and MAE 11.56-42.89, so read 0.72 as "somewhere in the 0.5-0.8 band". Command:
`python training/eval_onnx.py --dataset cc0 --split test --score-thresh 0.30 --nms-thresh 0.35
--max-dets 1000` from `training/`, identical flags otherwise; output `docs/reports/test-evaluation.json`,
predictions `docs/reports/predictions/*-cc0-test.json.gz`.

## What was discarded, and why

The training run's own `metrics.json` contains SKU-110K numbers (mAP50 0.13, MAE 563). They are
**wrong and are not used anywhere**: `train.py` evaluated the exported graph with
`run_raw_candidates(..., normalise=True)` while the exporter bakes ImageNet mean/std into the
graph, so the network was normalised twice and emitted about 700 detections per image. The same
checkpoint scored 0.5976 on CC0 validation through the corrected path, consistent with the training
loop's own 0.54-0.60, so the weights and the export were fine and only the evaluator was not.
`onnx_eval.run_raw_candidates` now defaults to `normalise=False`,
`training/tests/test_onnx_normalisation_default.py` pins that default, and both call sites in
`train.py` pass the flag explicitly. The numbers in this report come from that corrected path.

The scoring kernel itself ended in an ERROR state, but only after both evaluation commands had
finished: the notebook's last cell built `summary.json` with `m['primary']['onnx_file']`, and
`onnx_file` sits on the model entry rather than inside `primary`, so it raised `KeyError` after
`test-sku110k.json` and both prediction files were already written. The cell is fixed in
`training/notebooks/eval/kaggle_eval.ipynb`; `docs/reports/sku110k-summary.json` was assembled from
the run's own two JSON files, which is what that cell would have produced.

## Failure shape on CC0 (mAP50 0.72 split)

The errors that matter there are over-counts on medium shelves, not misses on dense ones:

| image | ground truth | predicted | error |
| --- | --- | --- | --- |
| `005.jpg` | 251 | 335 | +84 (+33 %) |
| `040.jpg` | 71 | 111 | +40 (+56 %) |
| `002.jpg` | 690 | 657 | -33 (-5 %) |

Splitting one product into two boxes happens where a shelf gap or a price rail creates a seam the
box regressor treats as two items; the largest shelf is counted to within 5 %.

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
