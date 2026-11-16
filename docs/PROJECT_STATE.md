# Project state

Last updated: 2026-11-16 (S0)

## What exists

- Repo hygiene: `.gitignore` (secrets, `private/`, assistant state, data, weights),
  `.gitattributes`, `.env.example` (names only), MIT `LICENSE`.
- Git hooks in `.githooks/` with logic in `scripts/hooks/`, shared rules in
  `scripts/lib/repo-rules.mjs`. `core.hooksPath` is set to `.githooks` locally.
- CI (`.github/workflows/ci.yml`): commit history check against GitHub accounts,
  tracked-file check, gitleaks over full history, repo script unit tests,
  `features.json` validation.
- Documentation system: `AGENTS.md`, pointer files, `docs/*`, `scripts/check-done.mjs`.
- Architecture decisions with free-tier terms checked on 2026-11-16 (`docs/DECISIONS.md`).

## What does not exist yet

- Datasets, training code, model, web app, chat, Python package. See `docs/features.json`.

## Tooling on the owner's machine (checked 2026-11-16)

node 24, pnpm 12, python 3.14, uv 0.13, vercel CLI 65, kaggle CLI 2.2, neonctl 8,
gh 2.103, git 2.56, gitleaks 8.30 (installed via winget). Docker is not installed.

## Blockers waiting on the owner

- Clerk app and keys, Kaggle account + phone verification + token, service keys in
  `private/.env.local`. Steps in `docs/OWNER_TODO.md`.
