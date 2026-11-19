# Model card: ShelfSense detector

Status: **validation measured, test pending.** Every number below was produced by running an
exported ONNX file on the CC0 validation split and scoring it with `pycocotools`. An earlier
version of this card listed simulated figures; they were removed (see [LESSONS.md](LESSONS.md)).

## Model

- `torchvision.models.detection.fcos_resnet50_fpn`, BSD-3-Clause, 32,064,455 parameters.
- COCO-pretrained backbone and FPN, classification head replaced for two classes
  (background, `item`), 640 px square input.
- Training: Kaggle Tesla T4, mixed precision, AdamW, cosine schedule, 6000 SKU-110K training
  images + 27 CC0 images, 12 epochs, batch 8, `detections_per_img=1000`,
  `topk_candidates=1500`.
- Export: ONNX opset 17 with the ImageNet normalisation and the anchor decoding inside the graph,
  output `[1, N, 6] = [xc, yc, w, h, score, 1]`; dynamic INT8 for the browser.

## Measured on validation (not on test)

Split: 9 CC0 supermarket shelf photos, 1,922 items, dHash-split from the same 45-image set as
training, 0 cross-split near-duplicate leaks.

| File | maxDets | mAP50 | mAP50-95 | count MAE | count MAPE |
| --- | --- | --- | --- | --- | --- |
| `improved-fcos-r50-fpn-v2-int8.onnx` | 1000 | 0.5309 | 0.2798 | 74.00 | 69.35 % |
| `improved-fcos-r50-fpn-v2-fp32.onnx` | 1000 | 0.5306 | 0.2816 | 72.67 | 68.43 % |
| `improved-fcos-r50-fpn-v2-fp32.onnx` | 100 | 0.3006 | 0.1813 | 132.44 | 80.32 % |

- Command and raw output: `docs/reports/validation-detection-cap.md`,
  `docs/reports/validation-cap-cc0-val.json`.
- Predictions behind those rows: `docs/reports/predictions/*-cc0-val.json.gz`.
- Kernel that trained the weights: `ibrahimhossainsumon/shelfsense-yolox-dense-shelf-training`,
  the first kernel before the detector name changed; superseded by
  `ibrahimhossainsumon/shelfsense-fcos-training`.
- Bootstrap 95 % intervals and per-density buckets are in the report JSON.

INT8 loses nothing measurable at this scale (mAP50 0.5309 vs 0.5306) with a quarter of the bytes,
so the browser build uses INT8 unless the test split says otherwise.

## Intended use

Counting packaged products on front-facing grocery shelf photos, and finding gaps between them.

## Not intended for

Brand or SKU recognition, reading price tags, counting stock hidden behind the front row,
people or faces, or any photo that is not a retail shelf. Not an inventory system of record.

## Limits

- **Two-epoch weights.** The numbers above come from the first two runs (2 and 3 epochs). They
  show the pipeline works; they are not a finished model.
- **Count error is the real weakness.** MAE 74 items per photo on shelves averaging 214 items.
- **Small validation set.** Nine images; treat differences under ±0.02 mAP50 as noise.
- **Domain.** SKU-110K is dominated by US, European and East Asian supermarkets. South Asian
  flexible pouches, hanging sachets and price-heavy shelves are under-represented.
- **Single image.** Anything stacked or occluded behind the front row cannot be counted.
- **Licence.** Weights are fine-tuned on SKU-110K, which is licensed for academic and
  non-commercial research only. See [DATA.md](DATA.md).
