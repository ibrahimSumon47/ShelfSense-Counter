# Project state

Last updated: 2026-11-16 (S1)

## What exists

- Repo hygiene: `.gitignore` (secrets, `private/`, assistant state, data, weights),
  `.gitattributes`, `.env.example` (names only), MIT `LICENSE`.
- Git hooks in `.githooks/` with logic in `scripts/hooks/`, shared rules in
  `scripts/lib/repo-rules.mjs`. `core.hooksPath` is set to `.githooks` locally.
- CI (`.github/workflows/ci.yml`): commit history check against GitHub accounts,
  tracked-file check, gitleaks over full history, repo script unit tests,
  `features.json` validation, and Python `training` unit tests via `uv` and `pytest`.
- Documentation system: `AGENTS.md`, pointer files, `docs/*`, `scripts/check-done.mjs`.
- Architecture & dataset decisions with free-tier terms and dataset licences checked on
  2026-11-16 (`docs/DECISIONS.md`, `docs/DATA.md`).
- Phase S1 data pipeline (`training/`):
  - `shelfsense_training.download`: Kaggle CLI downloader (`thedatasith/sku110k-annotations`
    and `humansintheloop/supermarket-shelves-dataset`), credential verifier, dry-run CLI.
  - `shelfsense_training.splits`: store/planogram/session grouping + 64-bit perceptual dHash
    near-duplicate clustering (`assign_leak_free_splits`, `find_cross_split_leak_pairs`).
  - `shelfsense_training.converters`: SKU-110K CSV, Supervisely JSON (product-only filter),
    and Pascal VOC XML parsers; normalized YOLO `.txt` and COCO `.json` exporters.
  - 13 unit tests in `training/tests/` passing under `pytest`.

## What does not exist yet

- Detector choice ADR (S2-01), Kaggle training notebook/job runner, trained ONNX weights,
  evaluation reports, Next.js web app, chat, Python CLI/FastAPI package. See `docs/features.json`.

## Tooling on the owner's machine (checked 2026-11-16)

node 24, pnpm 12, python 3.12/3.14, uv 0.13, vercel CLI 65, kaggle CLI 2.2, neonctl 8,
gh 2.103, git 2.56, gitleaks 8.30. Docker is not installed.

## Blockers waiting on the owner

- Clerk app and keys, Kaggle account + phone verification + token (`~/.kaggle/access_token`
  or `~/.kaggle/kaggle.json`), service keys in `private/.env.local`. Steps in `docs/OWNER_TODO.md`.
