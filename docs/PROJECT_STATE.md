# Project state

Last updated: 2026-11-17 (S4, S5, S6, S7, S8 unblocked items completed)

## What exists

- Repo hygiene: `.gitignore` (secrets, `private/`, assistant state, data, weights),
  `.gitattributes`, `.env.example` (names only), MIT `LICENSE`.
- Git hooks in `.githooks/` with logic in `scripts/hooks/`, shared rules in
  `scripts/lib/repo-rules.mjs`. `core.hooksPath` is set to `.githooks` locally.
- CI (`.github/workflows/ci.yml`): commit history check against GitHub accounts,
  tracked-file check, gitleaks over full history, repo script unit tests,
  web TypeScript unit tests (`apps/web/src/lib/shelfsense.test.ts`),
  `features.json` validation, Python `training` + `python` unit tests via `uv` and `pytest`,
  and CodeQL security analysis (`javascript-typescript`, `python`).
- Architecture, dataset, detector, and batch API hosting decisions (`docs/DECISIONS.md`
  ADR-001..ADR-010, `docs/DATA.md`): YOLOX (Apache-2.0) selected for dense retail shelves.
- Phase S1 & S2/S3 training and evaluation harness (`training/`):
  - Kaggle CLI downloader, store/source + 64-bit dHash near-duplicate splitter,
    SKU-110K / Supervisely / VOC converters, Kaggle GPU kernel stager, and 101-point
    COCO `mAP50` + count MAE/MAPE + density-stratified evaluator (`19 passed` in `pytest`).
- Phase S4 & S5 Next.js web application & bilingual database-tool chat (`apps/web/`):
  - Dark blue-grey slate theme + light theme toggle, natural English (`en`) and Bangla (`bn`)
    copy (`src/lib/i18n.ts`), Store → Aisle → Shelf structure, Neon Postgres DDL (`src/lib/schema.ts`).
  - Client-side image resize, YOLOX ONNX decoder + NMS (`src/lib/detector.ts`),
    shelf row clustering & empty-gap detector (`src/lib/gaps.ts`), RFC 4180 CSV exporter
    with formula-injection protection (`src/lib/csv.ts`).
  - Typed, user-scoped database tools (`lowest_shelves`, `compare_periods`, `store_summary`),
    numeric-grounding verifier, and 30-question bilingual evaluation (`15 EN + 15 BN`,
    **30/30 = 100%** tool & numeric grounding accuracy recorded in `docs/reports/chat-eval-s5.md`).
- Phase S6 Python package, CLI, and FastAPI batch app (`python/`):
  - `shelfsense count photo.jpg` CLI, `ShelfDetector` ONNX Runtime engine, row gap detector,
    FastAPI `/health`, `/v1/count`, `/v1/batch-count`, and `Dockerfile` (`4 passed` in `pytest`).
- Phase S7 security & isolation (`apps/web/src/lib/security.ts`):
  - Magic-byte image upload verifier (`JPEG`/`PNG`/`WebP`), sliding-window rate limiter,
    owner- vs staff-role threshold guard, per-user data isolation tests, and CodeQL workflow.
- Phase S8 portfolio documentation: `docs/DEMO_SCRIPT.md` and `docs/DEPLOY.md`.

## Blockers waiting on the owner (`docs/OWNER_TODO.md`)

All 31 unblocked features are **done** with committed evidence and tests. The remaining 17
items are `blocked` solely on external credentials in `docs/OWNER_TODO.md`:
1. **Item 2 (Kaggle API token + phone verification):** unblocks `S2-02..S2-07`, `S3-01..S3-05`, and `S8-01` (live Kaggle GPU training, ONNX export, test-set report).
2. **Items 1 & 3 (Clerk, Cloudinary, and Neon keys in `private/.env.local`):** unblocks `S4-02`, `S4-07`, `S4-12`, `S7-01`, `S7-02`, and `S8-01` (live Vercel production deploy and Playwright/axe/Lighthouse production audits).
