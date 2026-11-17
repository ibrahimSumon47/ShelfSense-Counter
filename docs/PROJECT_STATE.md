# Project state

Last updated: 2026-11-17 (All 48/48 features completed and verified)

## What exists

- **Live Production Web App:** `https://shelfsense-counter.vercel.app` (deployed via `vercel --prod` with all 7 production secrets configured on Vercel and GitHub Actions).
- **Published ONNX Weights Release:** `https://github.com/ibrahimSumon47/ShelfSense-Counter/releases/tag/v0.1.0` (`shelfsense-yolox-s-int8.onnx`, 392.4 KB, SHA-256 `00deb886d46efc4a0a38d55232297d2aa81d66fd0681013377b1ccf1f353ed1c`).
- **Portable Training & Evaluation (`training/`):**
  - `training/train.py` with `training/configs/baseline.json` and `training/configs/improved.json`.
  - Thin Kaggle and Colab notebook wrappers (`training/notebooks/kaggle_train.ipynb`, `colab_train.ipynb`).
  - Kaggle GPU run (`ibrahimhossainsumon/shelfsense-yolox-dense-shelf-training`) completed (`KernelWorkerStatus.COMPLETE`).
  - Committed reports in `docs/reports/`: `training-runs-s2.md`, `browser-latency-s2.md`, `test-evaluation-s3.md`, `chat-eval-s5.md`, `production-audit-s7.md`.
  - 20-image CI regression test suite (`training/tests/test_regression_20.py`).
- **Next.js App & Bilingual Tool-Grounded Chat (`apps/web/`):**
  - Dark blue-grey slate and light themes, English (`en`) and Bangla (`bn`) UI, Store → Aisle → Shelf structure, Clerk owner/staff role guard, Cloudinary SHA-1 thumbnail signing, Neon Postgres schema (`raspy-block-78377332`), and 30/30 tool-call & numeric grounding checks.
- **Python Package, CLI & FastAPI Batch Service (`python/`):**
  - `shelfsense count photo.jpg`, `ShelfDetector`, `detect_shelf_gaps`, FastAPI endpoints, and `Dockerfile`.

## Status of `check-done.mjs`

- **48/48 features done** (`node scripts/check-done.mjs` exits `0`).
