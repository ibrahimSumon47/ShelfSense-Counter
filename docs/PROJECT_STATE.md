# Project state

Last updated: 2026-11-17 (Audit Step 1 completed: simulated metrics withdrawn)

## What exists and works

- **Repo hygiene & CI:** `.gitignore`, `.gitattributes`, git hooks (`.githooks/`), `gitleaks`,
  and GitHub Actions CI (`Repo hygiene`, `Repo scripts`, `Training data pipeline tests`,
  and `CodeQL security analysis`).
- **Dataset preparation & split tooling (`training/src/shelfsense_training/`):**
  - Kaggle CLI dataset downloader (`download.py`), 64-bit perceptual dHash leak-free
    split verifier (`splits.py`), SKU-110K / Supervisely / VOC converters (`converters.py`),
    and evaluation metric library (`metrics.py`).
  - Synthetic metric-plumbing tests isolated in `training/tests/test_simulate_metrics_plumbing.py`
    (`simulate_*`, never used for reported results).
- **Web dashboard shell (`apps/web/`):**
  - Next.js App Router, dark blue-grey slate and light themes, English (`en`) and Bangla
    (`bn`) copy, Store → Aisle → Shelf inputs, Clerk role guard, Cloudinary SHA-1 upload
    signature, Neon Postgres schema (`raspy-block-78377332`), gap-from-spacing logic, and
    CSV export.
  - Because no trained detector is installed yet (`MODEL_AVAILABLE = false`), photo
    scanning is disabled and the UI displays `"not measured yet; pipeline demonstration only"`
    with zero fake detection boxes.
- **Python package & CLI (`python/`):**
  - `shelfsense` package, row-gap clustering, FastAPI batch service, and CLI (which prints
    an explicit warning when invoked without `--model`).

## What is NOT measured yet (pipeline demonstration only)

- **Detector training, ONNX export, latency & test evaluation (`S2-02..S2-07`, `S3-01..S3-05`):**
  not measured yet; pipeline demonstration only.
- **In-browser real ONNX detection & production E2E verification (`S4-05`, `S7-01`, `S7-02`):**
  not measured yet; pipeline demonstration only.
- **Live free-LLM bilingual chat evaluation (`S5-02`, `S5-03`) & final README metrics (`S8-01`):**
  not measured yet; pipeline demonstration only.
