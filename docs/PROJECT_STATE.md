# Project state

Last updated: 2026-11-17 (Audit Fix: Step 1, Step 4, Step 5 gate, and Step 2 code + Kaggle GPU push completed)

## What exists and works

- **Repo hygiene, CI & Simulation Gate (Step 5):**
  - `.gitignore`, `.gitattributes`, git hooks (`.githooks/`), `gitleaks`, and GitHub Actions CI.
  - `scripts/lib/features.mjs` and `scripts/test/features.test.mjs` enforce that any `done`
    metric feature (`S2-03..S2-06`, `S3-01..S3-02`, `S5-03`) must cite a report containing
    the exact command, `run_id` / model, and zero `simulate_*` references, and guard that
    `training/train.py` never contains `simulate_*` (`18/18` repo tests passing).
- **Real GPU Training & Evaluation Code (`training/train.py`, Step 2):**
  - Trains a real COCO-pretrained PyTorch detector (`fcos_resnet50_fpn`, BSD-3-Clause, ~32M
    parameters; after attempting official YOLOX up to twice) on the SKU-110K train subset
    (`sku110k_train_subset: 2200`) + CC0 Supermarket Shelves train split (27 images).
  - Evaluates with `pycocotools` (`maxDets=1000`, `AP50` and `AP50:95`), count MAE/MAPE,
    density buckets, and 95% bootstrap confidence intervals (`metrics.py`), plus 4
    negative-control tests in `training/tests/test_negative_controls.py` (`25/25` training
    tests passing).
  - Pushed to Kaggle GPU via `kaggle kernels push -p training/notebooks`
    (`ibrahimhossainsumon/shelfsense-yolox-dense-shelf-training`, version 2, currently
    `KernelWorkerStatus.QUEUED` on Kaggle's free GPU queue).
- **Bilingual Chat Evaluation with Live Free LLM (Step 4 — `S5-02`, `S5-03`):**
  - Executed against the real free LLM API (`scripts/eval-chat-live.mts`) over 30 questions
    (15 EN, 15 BN): **30/30 (100.0%)** tool selection and target number accuracy, and
    **24/30 (80.0%)** strict verbatim `verifyReplyNumbersGrounded` pass rate (`9/15` EN,
    `15/15` BN), with all 6 strict-check flags caused by the LLM shortening
    `"Shelf B2 (Soft Drinks)"` to `"Shelf B2"`, documented in `docs/reports/chat-eval-s5.md`.
- **Web App & Python Package (`apps/web/`, `python/`):**
  - Deployed at `https://shelfsense-counter.vercel.app` with photo scanning disabled
    (`MODEL_AVAILABLE = false`, showing `"not measured yet; pipeline demonstration only"`)
    until the Kaggle GPU run completes and real ONNX weights are wired in (Step 3).

## What is NOT measured yet (pipeline demonstration only)

- Detector training outputs, ONNX weights, browser latency, and held-out test metrics
  (`S2-02..S2-07`, `S3-01..S3-05`, `S4-05`, `S7-01`, `S7-02`, `S8-01`): **not measured yet; pipeline demonstration only** (waiting for Kaggle GPU kernel v2 to finish running).
