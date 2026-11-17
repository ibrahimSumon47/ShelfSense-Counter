# ShelfSense

Count what is on a retail shelf from a single photo.

> **Status: not measured yet; pipeline demonstration only.** No trained detector exists yet,
> so no accuracy figure is published and the public site does not analyse photos. An earlier
> version of this repository reported detection metrics that came from a simulation; they
> were withdrawn. The full account is in [docs/LESSONS.md](docs/LESSONS.md).

Live site (shows the interface only, no detection): https://shelfsense-counter.vercel.app

## Goal

Take or upload a picture of a grocery shelf and find each product, count them, mark gaps
and flag low stock per store, aisle and shelf, with a chat that answers questions about
stored scans in English or Bangla.

## What exists and works today

- Dashboard shell (English and Bangla, dark and light themes) with the detector disabled
  (`"not measured yet; pipeline demonstration only"`).
- Gap-from-spacing logic and CSV export, covered by unit tests (logic only, not accuracy).
- Leak-free dataset split tooling, annotation converters, `pycocotools` (`maxDets=1000`) +
  bootstrap 95% CI evaluator, and negative-control tests (`training/tests/test_negative_controls.py`),
  with 25 passing unit tests.
- Bilingual chat tool-call and numeric grounding checks (`docs/reports/chat-eval-s5.md`,
  `scripts/eval-chat-live.mts`): evaluated on 30 questions (15 English, 15 Bangla) against
  the live free LLM API (`30/30` tool selection and target number accuracy; `24/30 = 80.0%`
  strict verbatim grounding check, with all 6 English strict-check flags caused by the model
  abbreviating `"Shelf B2 (Soft Drinks)"` to `"Shelf B2"`, documented in
  [docs/reports/chat-eval-s5.md](docs/reports/chat-eval-s5.md)).
- A Python package and CLI. Without a model file the CLI uses a contrast heuristic that
  only works on clean synthetic images and prints a warning.
- Repository hygiene: single author, secret scanning, simulation-guard check in
  `scripts/check-done.mjs`, and CI.

## What does not exist yet

- Completed GPU training outputs (`S2-02..S2-07`, `S3-01..S3-05`): the real PyTorch
  COCO-pretrained detector training job (`training/train.py`) has been pushed to Kaggle GPU
  (`ibrahimhossainsumon/shelfsense-yolox-dense-shelf-training`, version 2) and is currently
  `QUEUED` on Kaggle's GPU worker pool. Until it finishes, detector metrics are
  **not measured yet; pipeline demonstration only**.
- In-browser real ONNX detection wired into the web app (`S4-05`, `S7-01`, `S7-02`).

The plan and status of each item are in [docs/features.json](docs/features.json) and
[docs/HANDOFF.md](docs/HANDOFF.md).

## Licences

Code is MIT ([LICENSE](LICENSE)). Datasets and any future weights follow
[docs/DATA.md](docs/DATA.md); SKU-110K is for non-commercial research only.
