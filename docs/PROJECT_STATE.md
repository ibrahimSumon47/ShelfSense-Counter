# Project state

Last updated: 2026-11-16 (S2-01 + Kaggle/eval harness)

## What exists

- Repo hygiene: `.gitignore` (secrets, `private/`, assistant state, data, weights),
  `.gitattributes`, `.env.example` (names only), MIT `LICENSE`.
- Git hooks in `.githooks/` with logic in `scripts/hooks/`, shared rules in
  `scripts/lib/repo-rules.mjs`. `core.hooksPath` is set to `.githooks` locally.
- CI (`.github/workflows/ci.yml`): commit history check against GitHub accounts,
  tracked-file check, gitleaks over full history, repo script unit tests,
  `features.json` validation, and Python `training` unit tests via `uv` and `pytest`.
- Documentation system: `AGENTS.md`, pointer files, `docs/*`, `scripts/check-done.mjs`.
- Architecture, dataset, and detector decisions (`docs/DECISIONS.md` ADR-001..ADR-010,
  `docs/DATA.md`): YOLOX (Apache-2.0) selected for dense retail shelves and browser ONNX.
- Phase S1 & S2/S3 training and evaluation harness (`training/`):
  - `shelfsense_training.download`: Kaggle CLI downloader (`thedatasith/sku110k-annotations`
    and `humansintheloop/supermarket-shelves-dataset`), credential verifier, dry-run CLI.
  - `shelfsense_training.splits`: store/planogram/session grouping + 64-bit perceptual dHash
    near-duplicate clustering (`assign_leak_free_splits`, `find_cross_split_leak_pairs`).
  - `shelfsense_training.converters`: SKU-110K CSV, Supervisely JSON (product-only filter),
    and Pascal VOC XML parsers; normalized YOLO `.txt` and COCO `.json` exporters.
  - `shelfsense_training.kaggle_job`: Kaggle GPU kernel metadata and staging (`kaggle kernels push`),
    training config, SHA-256 weight checksum helper.
  - `shelfsense_training.metrics`: IoU, NMS, 101-point COCO AP@0.50 (`mAP50`), count MAE,
    count MAPE (%), and stratification by shelf density (`sparse <50`, `medium 50-150`, `dense >150`).
  - 19 unit tests in `training/tests/` passing under `pytest`.

## What does not exist yet

- Live Kaggle GPU training runs and ONNX weight exports (`S2-02`..`S2-07`, `S3-01`..`S3-05`,
  currently `blocked` on the owner's Kaggle API token in `docs/OWNER_TODO.md` item 2).
- Next.js web app (`apps/web/`, S4), bilingual database-tool chat (S5), Python CLI and
  FastAPI package (`python/`, S6). See `docs/features.json`.

## Tooling on the owner's machine (checked 2026-11-16)

node 24, pnpm 12, python 3.12/3.14, uv 0.13, vercel CLI 65, kaggle CLI 2.2, neonctl 8,
gh 2.103, git 2.56, gitleaks 8.30. Docker is not installed.

## Blockers waiting on the owner

- Clerk app and keys, Kaggle account + phone verification + token (`~/.kaggle/access_token`
  or `~/.kaggle/kaggle.json`), service keys in `private/.env.local`. Steps in `docs/OWNER_TODO.md`.
