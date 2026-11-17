# Model card: ShelfSense detector

Status: **no trained model exists yet.** Nothing in this repository has been measured.

An earlier version of this card listed mAP50, count MAE and MAPE, an int8 file size and
latency. Those figures came from a simulation (ground-truth boxes with random jitter and
misses) and a randomly initialised ONNX file, not from a trained detector. They were
removed. See [LESSONS.md](LESSONS.md).

## Planned model

- A COCO-pretrained detector (official YOLOX, Apache-2.0) fine-tuned for a single class,
  "item", on shelf photos. If YOLOX cannot be installed, Ultralytics YOLO would be used and
  its AGPL-3.0 licence would apply to the weights and be stated here.
- Training data: the CC0 Supermarket Shelves set and a subset of SKU-110K (non-commercial
  research licence; weights trained on it inherit that restriction). See [DATA.md](DATA.md).

## Intended use

Counting packaged products on grocery shelf photos and finding gaps between items.

## Not intended for

Brand or SKU recognition, people, or anything outside retail shelves.

## Metrics

Not measured yet; pipeline demonstration only.

## Limits

Unknown until a real evaluation exists. Photos of stock stacked behind the front row cannot
be counted from a single image, whatever the model.
