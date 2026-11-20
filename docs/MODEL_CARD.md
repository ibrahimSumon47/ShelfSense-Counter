# Model card: ShelfSense detector

Status: **measured on validation and test.** Every number below was produced by running an exported
ONNX file on real images and scoring it with `pycocotools`; the commands and the committed
prediction files are named next to the numbers. An earlier version of this card listed simulated
figures; they were removed (see [LESSONS.md](LESSONS.md)).

## Model

- `torchvision.models.detection.fcos_resnet50_fpn`, BSD-3-Clause, 32,064,455 parameters.
- COCO-pretrained backbone and FPN, classification head replaced for two classes
  (background, `item`), 640 px square input.
- Training: Kaggle Tesla T4, mixed precision, AdamW, cosine schedule, 6,036 images
  (6,009 SKU-110K + 27 CC0), 12 epochs, batch 8, `detections_per_img=1000`,
  `topk_candidates=1500`, 12,658 s wall clock.
- Export: ONNX opset 17 with the ImageNet normalisation and the anchor decoding inside the graph,
  output `[1, N, 6] = [xc, yc, w, h, score, 1]`; dynamic INT8 for the browser.
- Weights: kernel `ibrahimhossainsumon/shelfsense-fcos-training`, version 1, checkpoint `best.pt`
  from epoch 8 of 12. Published in release `v1.0.0`.

## Measured results

Thresholds (score 0.30, NMS 0.35, maxDets 1000) were fixed on SKU-110K validation by count MAE
before any test image was scored. Full tables, intervals and the per-density breakdown:
[docs/reports/test-evaluation.md](reports/test-evaluation.md).

**SKU-110K test, 200 images, 29,092 items, scored once:**

| File | mAP50 | mAP50-95 | count MAE | count MAPE |
| --- | --- | --- | --- | --- |
| `fcos-r50-fpn-v3-int8.onnx` (32.8 MB) | 0.8418 | 0.4844 | 26.52 | 21.29 % |
| `fcos-r50-fpn-v3-fp32.onnx` (128.7 MB) | 0.8418 | 0.4851 | 26.55 | 21.30 % |

95 % bootstrap intervals: int8 mAP50 0.8171-0.8649 and count MAE 23.18-30.18; fp32 0.8163-0.8648
and 23.20-30.25.

**SKU-110K validation, 200 images, 30,119 items:** int8 mAP50 0.8524, count MAE 27.68; fp32 0.8602,
27.68.

**CC0 Supermarket Shelves test, 9 images, 1,950 items, scored once:** int8 mAP50 0.7215, count MAE
25.67, MAPE 19.91 %; fp32 0.7227, 26.56, 20.68 %. Nine images give a 95 % interval of mAP50
0.5324-0.8196, so treat this as a coarse check on a second store, not a precise figure.

**In the deployed browser**, WASM, int8 graph: `002.jpg` (690 items) counted 663 products in
3,996 ms, against 657 from the Python fp32 path on the same image.

Reproducing any row needs only the committed prediction files in `docs/reports/predictions/` and
`pycocotools`; the report carries the exact commands and the rescoring recipe.

## Intended use

Counting packaged products on front-facing grocery shelf photos, and finding gaps between them, to
estimate what is on a shelf and what is missing. Research, portfolio and demonstration use.

## Not intended for

Brand or SKU recognition, reading price tags, counting stock hidden behind the front row, people or
faces, or any photo that is not a retail shelf. Not an inventory system of record: the count error
is about 21 % of the true count, so it cannot drive reordering on its own.

## Limits

- **Count error is the real weakness.** MAPE 21.3 % on SKU-110K test, MAE 26.5 items per photo.
  mAP50 0.84 means the boxes land on products; it does not mean the count is right.
- **Sparse shelves fail badly.** The one test image with under 50 items was counted at about four
  times the truth (MAE 140 on a ~42-item shelf), because the model fires a packed-shelf number of
  candidates regardless of how empty the shelf is.
- **Density matters.** mAP50 is 0.778 on shelves with over 150 items (count error 12.8 %) and 0.886
  on 50-150 items (23.1 %), so dense, evenly packed shelves are the strong case.
- **Domain.** SKU-110K is dominated by US, European and East Asian supermarkets. South Asian
  flexible pouches, hanging sachets and price-heavy shelves are under-represented; the CC0 store
  (a different retailer) scores 0.72 mAP50 rather than 0.84.
- **Single image.** Anything stacked or occluded behind the front row cannot be counted.
- **INT8 is not a compromise here.** It matches fp32 within 0.001 mAP50-95 on both splits and is
  what the browser ships.
- **Licence.** Weights are fine-tuned on SKU-110K, which is licensed for academic and
  non-commercial research only. See [DATA.md](DATA.md). The detector architecture is BSD-3-Clause;
  the code in this repository is MIT.
