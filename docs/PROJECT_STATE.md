# Project state

Last updated: 2026-11-17 (S6 completed)

## What exists

- Repo hygiene: `.gitignore` (secrets, `private/`, assistant state, data, weights),
  `.gitattributes`, `.env.example` (names only), MIT `LICENSE`.
- Git hooks in `.githooks/` with logic in `scripts/hooks/`, shared rules in
  `scripts/lib/repo-rules.mjs`. `core.hooksPath` is set to `.githooks` locally.
- CI (`.github/workflows/ci.yml`): commit history check against GitHub accounts,
  tracked-file check, gitleaks over full history, repo script unit tests,
  `features.json` validation, and Python `training` + `python` unit tests via `uv` and `pytest`.
- Documentation system: `AGENTS.md`, pointer files, `docs/*`, `scripts/check-done.mjs`.
- Architecture, dataset, detector, and batch API hosting decisions (`docs/DECISIONS.md`
  ADR-001..ADR-010, `docs/DATA.md`): YOLOX (Apache-2.0) selected for dense retail shelves.
- Phase S1 & S2/S3 training and evaluation harness (`training/`):
  - `shelfsense_training.download`: Kaggle CLI downloader, credential verifier, dry-run CLI.
  - `shelfsense_training.splits`: store/planogram/session grouping + 64-bit perceptual dHash
    near-duplicate clustering (`assign_leak_free_splits`, `find_cross_split_leak_pairs`).
  - `shelfsense_training.converters`: SKU-110K CSV, Supervisely JSON, and Pascal VOC XML
    parsers; normalized YOLO `.txt` and COCO `.json` exporters.
  - `shelfsense_training.kaggle_job`: Kaggle GPU kernel metadata and staging, SHA-256 checksums.
  - `shelfsense_training.metrics`: IoU, NMS, 101-point COCO AP@0.50 (`mAP50`), count MAE,
    count MAPE (%), and stratification by shelf density (`sparse <50`, `medium 50-150`, `dense >150`).
  - 19 unit tests in `training/tests/` passing under `pytest`.
- Phase S6 Python package, CLI, and FastAPI batch app (`python/`):
  - `shelfsense.gaps`: shelf row clustering (`cluster_shelf_rows`) and empty-gap detection
    (`detect_shelf_gaps`).
  - `shelfsense.detector`: ONNX Runtime inference session (`ShelfDetector`), letterbox
    preprocessor, NMS, and `ScanAnalysis`.
  - `shelfsense.cli`: `shelfsense count photo.jpg [--json] [--threshold N]` CLI.
  - `shelfsense.api` and `python/Dockerfile`: FastAPI `/health`, `/v1/count`, and
    `/v1/batch-count` endpoints with MIME and 10 MB size validation.
  - 4 unit tests in `python/tests/test_shelfsense.py` passing under `pytest`.

## What does not exist yet

- Next.js web app (`apps/web/`, S4), bilingual database-tool chat (S5), quality/security
  checks (S7), and portfolio docs (S8).
- Live Kaggle GPU training runs and ONNX weight exports (`S2-02`..`S2-07`, `S3-01`..`S3-05`,
  currently `blocked` on the owner's Kaggle API token in `docs/OWNER_TODO.md` item 2).

## Tooling on the owner's machine (checked 2026-11-16)

node 24, pnpm 12, python 3.12/3.14, uv 0.13, vercel CLI 65, kaggle CLI 2.2, neonctl 8,
gh 2.103, git 2.56, gitleaks 8.30. Docker is not installed.

## Blockers waiting on the owner

- Clerk app and keys, Kaggle account + phone verification + token (`~/.kaggle/access_token`
  or `~/.kaggle/kaggle.json`), service keys in `private/.env.local`. Steps in `docs/OWNER_TODO.md`.
