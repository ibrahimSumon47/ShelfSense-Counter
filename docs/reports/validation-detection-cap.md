# Validation re-evaluation: the 100-detection cap and two export defects

Status: measured. Every number below comes from running the stored ONNX files on the CC0
validation split and scoring the output with `pycocotools`. Nothing was simulated or
perturbed.

## Where the models came from

| Run id | Kaggle kernel | Version | Weights file (local, gitignored) |
| --- | --- | --- | --- |
| `baseline-fcos-r50-fpn-v1` | `ibrahimhossainsumon/shelfsense-yolox-dense-shelf-training` | 2 | `baseline-fcos-r50-fpn-v1-{fp32,int8}.onnx` |
| `improved-fcos-r50-fpn-v2` | `ibrahimhossainsumon/shelfsense-yolox-dense-shelf-training` | 3 | `improved-fcos-r50-fpn-v2-{fp32,int8}.onnx` |

Both are torchvision `fcos_resnet50_fpn` (BSD-3-Clause) fine-tuned for one class, exported at
640 px. The baseline run trained 2 epochs on 827 images; the improved run trained 3 epochs on
2,027 images at 800 px but its ONNX export was taken at 640 px (the exporter ignored the
configured input size — fixed in `training/src/shelfsense_training/export.py`). The improved
run's `metrics.json` and log were never downloaded from Kaggle, so the only surviving evidence
for it is the ONNX files themselves, which is what this report evaluates.

## The split

`training/src/shelfsense_training/data.py` splits the 45 CC0 Supermarket Shelves images by
perceptual dHash into 27 train / 9 validation / 9 test, with 0 near-duplicate leaks across
splits. Validation holds 1,922 ground-truth items — an average of 214 items per image, i.e.
these are the dense shelves the model is for. Nine images is a small validation set and every
difference below is reported with that caveat.

## Command

```
python training/eval_onnx.py \
  --onnx training/outputs/outputs/baseline/baseline-fcos-r50-fpn-v1-fp32.onnx \
         training/outputs/outputs/baseline/baseline-fcos-r50-fpn-v1-int8.onnx \
         training/outputs/outputs/improved/improved-fcos-r50-fpn-v2-fp32.onnx \
         training/outputs/outputs/improved/improved-fcos-r50-fpn-v2-int8.onnx \
  --dataset cc0 --split val --input-size 640 --normalise yes --center-fix legacy \
  --score-thresh 0.25 --nms-thresh 0.45 --max-dets 100 1000 \
  --out docs/reports/validation-cap-cc0-val.json \
  --predictions-dir docs/reports/predictions
```

Raw output is in `docs/reports/validation-cap-cc0-val.json`. The prediction boxes behind every
row are committed as `docs/reports/predictions/*-cc0-val.json.gz` (37 KiB each), so the numbers
can be recomputed without the model:

```
python - <<'PY'
import gzip, json
from shelfsense_training.metrics import DetectionBox, ImageEvalInput
from shelfsense_training.coco_eval import coco_ap
d = json.load(gzip.open("docs/reports/predictions/improved-fcos-r50-fpn-v2-fp32-cc0-val.json.gz"))
inputs = [
    ImageEvalInput(
        image["image_id"],
        tuple(DetectionBox(*b, 1.0) for b in image["ground_truth"]),
        tuple(DetectionBox(*b) for b in image["predictions"]),
    )
    for image in d["images"]
]
print(coco_ap(inputs, max_dets=1000))
PY
```

## Result 1: the default 100-detection cap is the count ceiling

Same files, same thresholds (score 0.25, NMS 0.45), only the number of boxes kept per image
changes:

| Model | maxDets | mAP50 | mAP50-95 | count MAE | count MAPE | predictions / 1,922 items |
| --- | --- | --- | --- | --- | --- | --- |
| baseline fp32 | 100 | 0.2823 | 0.1484 | 132.44 | 80.32 % | 900 |
| baseline fp32 | 1000 | **0.5010** | **0.2331** | 141.89 | 109.09 % | 3,199 |
| baseline int8 | 100 | 0.2757 | 0.1481 | 132.44 | 80.32 % | 900 |
| baseline int8 | 1000 | 0.4996 | 0.2330 | 142.78 | 110.46 % | 3,207 |
| improved fp32 | 100 | 0.3006 | 0.1813 | 132.44 | 80.32 % | 900 |
| improved fp32 | 1000 | **0.5306** | **0.2816** | 72.67 | 68.43 % | 2,532 |
| improved int8 | 100 | 0.3006 | 0.1793 | 132.44 | 80.32 % | 900 |
| improved int8 | 1000 | **0.5309** | 0.2798 | 74.00 | 69.35 % | 2,550 |

Five of the nine validation images produced exactly 100 boxes and no more: with the cap at
100 the count error is dominated by undercounting (900 predictions for 1,922 items), and mAP50
falls by 0.22 to 0.23 because the highest-scoring 100 candidates are not the 100 that match
best on a shelf of 200+ items. The cap, not the detector, was the ceiling.

Raising the cap alone overshoots at score 0.25 (3,199 boxes for 1,922 items), so the score
threshold has to be tuned with it. Raising the cap does not fix counting by itself.

The earlier PyTorch-side reading for the baseline run, `mAP50 = 0.4731` on this split, is within
0.03 of the 0.5010 measured here from the ONNX file. The remaining difference comes from the
export defects below; the ONNX number is the one that describes the shipped artefact.

## Result 2: two defects in the first ONNX exports

The same three images' worth of weights, decoded four ways (2 × 2), mAP50 on validation:

| Preprocessing | Anchor centre fix | mAP50 | count MAE |
| --- | --- | --- | --- |
| ImageNet mean/std outside the graph | none | 0.3466 | 143.89 |
| ImageNet mean/std outside the graph | shift back half a cell | **0.4984** | 143.00 |
| raw 0-1 input | none | 0.2928 | 65.78 |
| raw 0-1 input | shift back half a cell | 0.4620 | 65.44 |

Both defects were then confirmed in the torchvision source rather than inferred from accuracy:

1. **Missing normalisation.** The export wrapper called `backbone` directly, so
   `GeneralizedRCNNTransform` — which normalises with the ImageNet mean and standard deviation
   during training — never ran inside the graph.
2. **Half-cell anchor offset.** torchvision's `AnchorGenerator.grid_anchors` places anchors at
   `arange(grid) * stride` and `BoxLinearCoder.decode(normalize_by_size=True)` scales the
   regression distances by the full anchor size. The exporter used `(g + 0.5) * stride`, which
   shifted every box half a cell down and right.

`training/src/shelfsense_training/export.py` now bakes the normalisation into the graph and
decodes `g * stride`, so newly exported files need neither correction. `training/eval_onnx.py`
keeps `--normalise` and `--center-fix legacy` only so the two stored runs above stay
reproducible.

## Result 3: threshold sweep on validation (improved fp32, maxDets 1000)

```
python training/eval_onnx.py --onnx training/outputs/outputs/improved/improved-fcos-r50-fpn-v2-fp32.onnx \
  --dataset cc0 --split val --input-size 640 --normalise yes --center-fix legacy \
  --score-thresh 0.3 --nms-thresh 0.45 --max-dets 1000 \
  --grid 0.2,0.3,0.4,0.5:0.35,0.45,0.55 --out docs/reports/validation-sweep-cc0-val.json
```

| score | NMS | mAP50 | count MAE |
| --- | --- | --- | --- |
| 0.2 | 0.35 | 0.5276 | 57.56 |
| 0.2 | 0.45 | **0.5306** | 110.56 |
| 0.2 | 0.55 | 0.5271 | 202.67 |
| 0.3 | 0.35 | 0.5222 | **34.33** |
| 0.3 | 0.45 | 0.5259 | 34.78 |
| 0.3 | 0.55 | 0.5225 | 58.67 |
| 0.4 | 0.35 | 0.4924 | 71.22 |
| 0.4 | 0.45 | 0.4990 | 65.56 |
| 0.4 | 0.55 | 0.4971 | 55.78 |
| 0.5 | 0.35 | 0.4250 | 102.78 |
| 0.5 | 0.45 | 0.4248 | 102.22 |
| 0.5 | 0.55 | 0.4246 | 101.44 |

On nine images the mAP50 differences between score 0.2 and 0.3 (0.531 vs 0.526) are not
meaningful, while the count error is four times better at 0.3 (MAE 34 vs 111). For a counting
product the second number decides: **score 0.30, NMS 0.35, maxDets 1000**. This is a validation
choice only; the test split is untouched and is evaluated once, after the next training run,
with thresholds chosen on the 200-image SKU-110K validation split.

## What changed because of this report

- `detections_per_img = 1000` and `topk_candidates = 1500` in `training/configs/fcos-dense-v3.json`
  (was torchvision's default of 100).
- The exporter normalises inside the graph and decodes `g * stride`.
- Train and evaluation both report through `onnx_eval.py`, so the reported number is produced by
  the same decoding the browser uses.
- INT8 versus FP32 on validation: mAP50 0.5309 vs 0.5306 for the improved run and 0.4996 vs
  0.5010 for the baseline, i.e. no measurable accuracy loss at this scale, with 32.8 MB instead
  of 128.7 MB. The decision for the shipped weights is taken again on the test split.
