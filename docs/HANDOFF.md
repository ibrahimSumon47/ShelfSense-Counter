# Handoff

Last updated: 2026-11-20 10:10Z (48/48; Root Directory fixed to `apps/web`, but Vercel blocked the
team for fair use, so the production alias answers 402 - `check-done` exits 0)

## Where things stand

Every deliverable in `docs/features.json` is done with evidence that a reader can re-run.
`node scripts/check-done.mjs` exits 0. The measured model numbers, the release, the deployment and
the production checks are all recorded:

| What | Where |
| --- | --- |
| Detector results (SKU-110K val and test, CC0 test) | `docs/reports/test-evaluation.md`, `docs/reports/sku110k-*.json` |
| Published weights | release `v1.0.0`, checksums in `sha256sums.txt` |
| Live site | https://shelfsense-counter.vercel.app - deployment `shelfsense-counter-pogxu6nig`, currently answering **402, blocked by Vercel** (`docs/OWNER_TODO.md` item 4) |
| Flows, axe, Lighthouse | `docs/reports/production-checks.md` and the JSON files beside it |
| Model limits and licence | `docs/MODEL_CARD.md` |
| README numbers and commands | `README.md` |

## Re-running the production checks

```
pnpm exec playwright test             # 13 checks, about two minutes, needs the 32.8 MB model
node scripts/lighthouse-report.mjs    # mobile and desktop, rewrites the three JSON files
```

Both target production by default; `SHELFSENSE_URL=http://localhost:3000` runs them against a local
build with `pnpm --filter @shelfsense/web start`. They are deliberately not CI jobs: the upload
flows would pull 33 MB three times per push, while CI already scores the 20-image regression bundle
against the released ONNX file, which is the check that belongs on every commit.

If a flow fails on the upload step, check whether it waited for `#photo-upload` to become enabled.
The input is disabled until `/models/manifest.json` resolves; a file that arrives before that now
produces a readable alert rather than being dropped silently, and one flow holds the manifest
request to prove it. If a local run fails with `400` on a `_next/static/chunks/...` file, an older
`next start` is probably still holding port 3000 and serving a build whose files were replaced - run
the new build on another port instead of killing that process. All eight axe
states in `docs/reports/axe-production.json` were captured on the live site on 2026-11-20.

## Deploying

The Vercel project's Root Directory is now `apps/web` (ADR-012), so a push to `main` builds the app
directory inside the pnpm workspace and deploys on its own. `ERR_PNPM_IGNORED_BUILDS` is fixed in
`pnpm-workspace.yaml`. A manual deploy still works the same way: `vercel deploy --prod --yes` from
`apps/web`.

This is configured but not yet proven end to end: the push that carried this change (`c96dda5`)
produced **no deployment at all** within four minutes, because Vercel stops creating Git-triggered
deployments while the team is blocked. The last deployment in the project is still `562c4c1` from
before the setting changed.

The site is offline: at 09:36Z on 2026-11-20 the alias began
answering `402 Payment Required` with `X-Vercel-Error: DEPLOYMENT_DISABLED`, and `vercel deploy`
printed `Your Team exceeded our fair use limits and has been blocked`. The deployment is READY and
aliased; Vercel is refusing to serve it and will not accept new deployments until the block is
cleared. That is owner item 4 in `docs/OWNER_TODO.md`. First step after it is lifted: push any
commit and confirm the git-triggered deployment goes READY, then re-run the flows, the axe scans and
`node scripts/lighthouse-report.mjs` against the alias.

## Blocked elsewhere

`GOOGLE_GENERATIVE_AI_API_KEY` is in the Vercel project but cannot be read back, and
`private/.env.local` is missing on this PC, so the live-LLM chat checks cannot be re-run here.
Exact owner steps are item 2b in `docs/OWNER_TODO.md`. The `S5-03` figures come from the run made
while the key was still available.

## Quota

Training used one GPU kernel run of about 3.5 h. Everything since then ran on CPU (the evaluation
kernel) or locally. No further GPU time is needed.

## If work continues

The honest next improvements, in the order they would matter:

1. **Sparse shelves.** The one SKU-110K test photo with under 50 items was counted at roughly four
   times the truth; a density-aware candidate cap would address it.
2. **Dense-shelf count error.** MAPE 21.3 % overall, 12.8 % on shelves above 150 items. A second
   training round (higher resolution, longer schedule) is the obvious lever, budgeted against the
   weekly Kaggle quota before starting.
3. **Brand and SKU recognition.** Out of scope for this model by design; a classifier head on the
   detected boxes would be a separate project with its own data licence question.
