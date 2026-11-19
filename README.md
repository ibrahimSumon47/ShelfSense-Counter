# ShelfSense

Count what is on a retail shelf from a single photo.

Live site: https://shelfsense-counter.vercel.app

> **Status: validation numbers measured, test numbers pending.** The detector is a real
> fine-tuned torchvision FCOS ResNet-50 FPN model (BSD-3-Clause, 32.06M parameters), trained on
> a Kaggle Tesla T4. Everything below was produced by running the exported ONNX file and scoring
> it with `pycocotools`; the commands are next to the numbers. The public site does not analyse
> photos yet, and the test split is evaluated exactly once, after the next training run finishes.
> An earlier version of this repository published simulated accuracy figures; they were withdrawn
> and the full account is in [docs/LESSONS.md](docs/LESSONS.md).

## Goal

Take or upload a picture of a grocery shelf, find each product, count them, mark empty gaps and
flag low stock per store, aisle and shelf, with a chat that answers questions about stored scans
in English or Bangla.

## What a visitor can do today

- Open the dashboard in English or Bangla, in a dark or light theme.
- See real empty, loading and error states, and read the help and demo script.
- Everything photo-related is explicitly disabled: the page says the detector is not published
  yet instead of showing invented boxes.

## Detector, measured on validation

Model: `fcos_resnet50_fpn` from torchvision, COCO-pretrained, fine-tuned for a single class
("item"). Training images: 2,027 (2,000 SKU-110K + 27 CC0) for the run below; the next run uses
6,000 SKU-110K images for 12 epochs at 640 px. Validation split: 9 CC0 supermarket shelf photos,
1,922 items, split from the same 45-image set by perceptual dHash with 0 cross-split leaks.

| Model file | maxDets | mAP50 | mAP50-95 | count MAE | count MAPE |
| --- | --- | --- | --- | --- | --- |
| `improved-fcos-r50-fpn-v2-int8.onnx` (32.8 MB) | 1000 | 0.5309 | 0.2798 | 74.00 | 69.35 % |
| `improved-fcos-r50-fpn-v2-fp32.onnx` (128.7 MB) | 1000 | 0.5306 | 0.2816 | 72.67 | 68.43 % |
| `baseline-fcos-r50-fpn-v1-fp32.onnx` (128.7 MB) | 1000 | 0.5010 | 0.2331 | 141.89 | 109.09 % |
| `improved-fcos-r50-fpn-v2-fp32.onnx` | 100 | 0.3006 | 0.1813 | 132.44 | 80.32 % |

Produced by (prediction files are committed, so the numbers can be recomputed without the model):

```
python training/eval_onnx.py \
  --onnx training/outputs/outputs/improved/improved-fcos-r50-fpn-v2-fp32.onnx \
  --dataset cc0 --split val --input-size 640 --normalise yes --center-fix legacy \
  --score-thresh 0.25 --nms-thresh 0.45 --max-dets 100 1000 \
  --out docs/reports/validation-cap-cc0-val.json \
  --predictions-dir docs/reports/predictions
```

Full tables, the threshold sweep and the cause of every difference:
[docs/reports/validation-detection-cap.md](docs/reports/validation-detection-cap.md).

Reading the numbers honestly:

- **The count error is still large.** MAE 74 items per photo on 214-item shelves is not a usable
  inventory count yet; it is a two-epoch model on 2,000 images. The next run trains 12 epochs on
  6,000 images.
- **mAP50 > 0.5 means the boxes land on products**, not that the count is right: at score 0.25
  the model returns more boxes than there are items, and only threshold tuning on validation
  brings the count down (MAE 34.3 at score 0.30, NMS 0.35).
- **Nine validation images are few.** Every difference within ±0.02 mAP50 here is noise.
- **No test number yet.** Reporting the test split once, after the next run, is the rule
  ([AGENTS.md](AGENTS.md)).

## What exists and works

- **Detector pipeline** (`training/`): leak-free dHash splits, annotation converters,
  resumable AMP training with a checkpoint every epoch, ONNX export with the normalisation and
  anchor geometry baked in, dynamic INT8 quantisation, and evaluation through `pycocotools`
  (`maxDets=1000`) with bootstrap confidence intervals and density buckets.
- **Dashboard** (English/Bangla, dark/light) with gap-from-spacing logic, CSV export, per-shelf
  saves and thresholds, all covered by unit tests (logic only, not detector accuracy).
- **Bilingual chat** with typed, user-scoped database tools: 30 questions (15 English,
  15 Bangla) scored `30/30` tool selection and numeric grounding, `24/30` on the stricter
  verbatim check ([docs/reports/chat-eval-s5.md](docs/reports/chat-eval-s5.md)).
- **Python package and CLI** (`uv run shelfsense count photo.jpg`) sharing the browser's exact
  decoding, plus a FastAPI batch endpoint.
- **Repository hygiene**: one author, secret scanning, commit and push hooks, and CI that also
  exports a tiny FCOS to ONNX on CPU before any GPU run is pushed.

## Architecture

```
photo ──► browser (Next.js, Vercel)
          │  client-side resize → 640×640 letterbox
          │  onnxruntime-web (WebGPU, WASM fallback)
          │      FCOS R50-FPN → [1, N, 6] candidates
          │      score threshold → NMS → cap 1000 → count
          ├── box overlay + per-shelf save ──► Neon Postgres (Drizzle), thumbnail via Cloudinary
          └── chat ──► typed tools ──► the same database (numbers only from tool results)

training (Kaggle T4) ──► checkpoints every epoch ──► ONNX FP32 + INT8 ──► GitHub Release
                               └── pycocotools evaluation on validation, test once
```

## Layout

| Path | What |
| --- | --- |
| `apps/web/` | Next.js app: capture, in-browser detection, history, chat |
| `python/` | `shelfsense` package, CLI and FastAPI app |
| `training/` | dataset scripts, training, ONNX export and evaluation |
| `scripts/` | repo tooling, hooks logic, CI checks, `check-done.mjs` |
| `docs/` | state, decisions, data card, model card, reports |

## Licences

- Code: MIT ([LICENSE](LICENSE)).
- Detector: torchvision FCOS, BSD-3-Clause, including the COCO-pretrained backbone weights.
- SKU-110K: academic and non-commercial research use only, so weights fine-tuned on it carry
  that restriction and the published model is a research and portfolio artefact.
- Supermarket Shelves (Humans in the Loop): CC0 1.0 public domain.

Details: [docs/DATA.md](docs/DATA.md), [docs/MODEL_CARD.md](docs/MODEL_CARD.md).
