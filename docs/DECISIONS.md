# Decisions

Short architecture decision records. Newest at the bottom. Each service decision
records the free-tier terms as checked on the given date; re-check before first use
in the slice that depends on it and append the result here.

---

## ADR-001 Single branch, owner-only history (2026-11-16)

**Decision.** `main` is the only branch. Every commit is authored and committed by the
owner's global git identity. No trailers, no co-authors, no tool or bot names.

**Enforcement.** `.githooks/commit-msg` (message rules), `.githooks/pre-commit`
(forbidden paths + gitleaks on staged changes), `.githooks/pre-push` (identity, trailers,
main only). CI repeats the checks against GitHub's own view: each commit's author account
must be `ibrahimSumon47`, and `main` must be the only branch. All rules live in
`scripts/lib/repo-rules.mjs` so hooks and CI cannot drift apart.

**Why.** The repository is a portfolio piece; the contributor list must show one person.

---

## ADR-002 Monorepo layout (2026-11-16)

`apps/web` (Next.js), `python/` (package, CLI, FastAPI), `training/` (data and Kaggle
jobs), `scripts/` (repo tooling), `docs/`. One repo keeps the model, the web app and the
evaluation numbers versioned together, so a README number always points at a commit.

---

## ADR-003 Inference runs in the browser (2026-11-16, to be confirmed by S2-06)

**Decision.** The detector is exported to ONNX, quantized, and run with
`onnxruntime-web` (WebGPU when available, WASM otherwise).

**Why.** No server hours to pay for, photos never leave the device, and the free hosting
tiers below have no GPU. Server-side inference is only reconsidered if S2-06 measures
that a mid-range phone cannot finish a scan in reasonable time (target: under 3 s on
WASM for a 640 px input). The measurement goes in `docs/reports/`.

**Consequence.** Only a small thumbnail and the detection JSON are sent to the server.
The thumbnail is resized on the client and uploaded straight to Cloudinary with a signed
request, so Vercel's 4.5 MB request body limit is never in the path.

---

## ADR-004 Hosting and services, free terms checked (2026-11-16)

Checked with a web search of each vendor's pricing/limits pages on 2026-11-16.

| Service | Use | Free terms found | Risk / note |
| --- | --- | --- | --- |
| Vercel Hobby | Next.js hosting | $0, 100 deployments/day, 4.5 MB function body, 100 GB transfer/month, 300 s max duration | Hobby is for personal, non-commercial use. A portfolio demo fits; client work would not. |
| Neon Free | Postgres | $0, no card, 100 CU-hours per project per month, 1 GB storage per project, scale to zero after 5 min, no automatic overage charges | Compute suspends until next month if exhausted. Keep queries light. |
| Clerk Free | Auth | $0, 50,000 monthly retained users per app | Roles are stored in our own database, not Clerk Organizations, to avoid depending on paid features. |
| Cloudinary Free | Scan thumbnails only | $0, no card, 25 credits/month (1 credit = 1 GB storage or 1 GB bandwidth or 1,000 transforms), soft limits | Thumbnails capped around 320 px and ~30 KB, so usage stays far below the pool. |
| Google AI Studio (free tier) | Chat with tool calling | $0, function calling on Flash and Flash-Lite models, rate limits per project shown in the AI Studio dashboard (low RPM/RPD) | Free-tier prompts may be used by the provider to improve products. Only aggregated scan numbers are sent, never photos or personal data. Rate limit handled with a clear "busy, try again" message. |
| Kaggle | One-off GPU training | Free with phone verification; weekly GPU quota around 30 h (T4 x2 or P100), 12 h max per session | A quota, not a trial. Each run report records hours used. |
| GitHub | Code, CI, Releases | Public repo: Actions minutes free; Releases hold files up to 2 GB each | Weights go to a Release asset. Re-verify at S2-07. |

**Excluded.** Render free (hours used by another project) and Hugging Face Spaces (no
longer free for new accounts), as instructed by the owner. Groq is a possible fallback
for chat but is not verified yet; it is not used until its terms are checked and logged.

---

## ADR-005 Chat answers only from database tools (2026-11-16)

The chat model gets a fixed set of typed tools (for example `lowest_shelves(date)`,
`compare_periods(a, b)`), each scoped to the signed-in user's stores. The system prompt
forbids stating any number that did not come back from a tool in the same turn, and the
server checks that every number in the reply appears in a tool result before showing it.
If a tool returns no rows the reply says the data is missing. Evaluated on 30 questions
(15 English, 15 Bangla) in S5-03.

---

## ADR-006 Detector licence policy (2026-11-16, proposed; decided in S2-01)

Ultralytics YOLO code and weights are AGPL-3.0, which would pull the web app under AGPL.
Prefer a permissively licensed detector if validation accuracy is comparable:

- YOLOX (Apache-2.0), strong on dense small objects, simple ONNX export.
- RT-DETR / D-FINE (Apache-2.0), good accuracy; query count must be raised for shelves
  with several hundred items.

Candidates are compared on the validation split only. If AGPL ends up clearly better,
the README and MODEL_CARD state the licence plainly. Dataset licences also bind the
weights: if a training set is non-commercial, the published weights are too.

---

## ADR-007 Code licence (2026-11-16)

Source code is MIT. Model weights and any derived data follow the licences of the
training datasets (see `docs/DATA.md`), which may be stricter than MIT.

---

## ADR-008 Python batch API hosting (2026-11-16, open)

The FastAPI app ships with a Dockerfile. It is deployed only if a host with a genuine
free-forever tier (no card) is verified in S6-03; otherwise `docs/DEPLOY.md` documents
how to run it locally or on the owner's own machine.

---

## ADR-009 Dataset selection and licensing (2026-11-16)

**Decision.** Use **SKU-110K** (*Goldman et al., CVPR 2019*) as the primary dense retail
shelf benchmark and **Supermarket Shelves Dataset** (*Humans in the Loop*) as the
CC0-licensed grocery shelf dataset.

**Verified terms (2026-11-16):**

- **SKU-110K:** 11,762 images (~147.4 items/image). Academic and non-commercial research
  licence (Trax Retail / CC BY-NC-SA 3.0 on mirrors). Accessible via the Kaggle CLI
  (`thedatasith/sku110k-annotations`, `mohamedessam3112002/sku-110k`) or the official
  S3 archive (`http://trax-geometry.s3.amazonaws.com/cvpr_challenge/SKU110K_fixed.tar.gz`).
- **Supermarket Shelves Dataset (Humans in the Loop):** 45 high-resolution images
  (~260.9 boxes/image across `Product` and `Price`; filtered to `Product`). Released
  under **CC0 1.0 Public Domain** on Kaggle (`humansintheloop/supermarket-shelves-dataset`).

**Why.** Combining SKU-110K's scale with a CC0 supermarket dataset gives both standard
benchmark comparability and a clean commercial-permissive option (`docs/DATA.md`).
Splits follow store/source boundaries and are verified by a 64-bit perceptual dHash
cross-split check before training.

