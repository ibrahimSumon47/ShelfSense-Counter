# AGENTS.md

Working rules for anyone (person or coding assistant) changing this repository.
Read this first, every session. The repository is the only memory.

## Start of every session

1. Read `AGENTS.md`, `docs/PROJECT_STATE.md`, `docs/features.json`, `docs/HANDOFF.md`.
2. Run `node scripts/check-done.mjs`. It prints the next open item and the model tag.
3. Tell the owner the tag in the form `[MODEL: Name, LEVEL]` before starting the slice.
4. Check identity: `git config user.name`, `git config user.email`, `gh auth status`
   (must be `ibrahimSumon47`). Never change them.
5. Check hooks: `git config core.hooksPath` must print `.githooks`.
   If not: `git config core.hooksPath .githooks`.

## End of every slice

1. Tests green locally (`node --test "scripts/test/*.test.mjs"` plus the slice's own tests).
2. Update `docs/features.json` (status + evidence), `docs/PROJECT_STATE.md`,
   `docs/HANDOFF.md` (exact next step + model tag), and `docs/LESSONS.md` if something went wrong.
3. `git status` and `git diff --cached --stat` before committing. Read the file list.
4. One push per finished slice. At most 8 pushes per session.
5. After every push:
   - `git log --format='%h %an <%ae>' -5`
   - `gh api repos/ibrahimSumon47/ShelfSense-Counter/contributors --jq '.[].login'`
   - The list must be only `ibrahimSumon47`. If anything else appears, stop feature
     work, rewrite history (git filter-repo), `git push --force-with-lease origin main`,
     verify again and log it in `docs/LESSONS.md`.
6. Wait for CI to pass (`gh run watch`), fix before moving on.

## Model guide (store the tag on every item in features.json)

| Work | Tag |
| --- | --- |
| Phase 0, architecture | `[MODEL: Claude Opus 5.5, HIGH]` |
| Bulk code | `[MODEL: Gemini 4 Argon, MID]` |
| Evaluation, security, stubborn bugs | `[MODEL: Claude Sonnet 5.5, MID]` |
| Docs and small edits | `[MODEL: Gemini 3.8 Flash, LOW]` |

## Git rules (non-negotiable)

- Only the owner's global git identity authors commits. No `--author`, no `--trailer`.
- No `Co-authored-by`, no "Generated with", no tool, assistant or bot names in commit
  messages, file headers or the README. `.githooks/commit-msg` enforces it.
- Branch `main` only. No other branches, pull requests, forks, dependency bots,
  GitHub Apps, or workflows that commit back. `.githooks/pre-push` and CI enforce it.
- Commit messages: short, plain, imperative ("Add gap detection for shelf rows").

## Sensitive files never go to GitHub

- `.env*` (except `.env.example`), keys, tokens, `kaggle.json`, `private/`,
  editor and assistant state folders, datasets, model weights, raw uploads, personal data.
- `.gitignore` covers them; `.githooks/pre-commit` refuses them and runs gitleaks;
  CI runs `scripts/check-repo-files.mjs` and gitleaks over full history.
- Weights go to a GitHub Release (`gh release create`). Datasets are downloaded by script.
- Secrets live in `private/.env.local`. Push them with `gh secret set NAME < file`
  and `vercel env add NAME production`. Never print them, never paste them in docs.

## Free forever only

- No trials, no card, no expiring credits, no watermarks.
- Before relying on a service, read its current pricing/terms and record the finding
  with the date in `docs/DECISIONS.md`.
- Not allowed: Render free tier (hours used by another project), Hugging Face Spaces.
- Kaggle GPU is a weekly quota; record usage in the run reports.

## CLI first

Use `gh`, `vercel`, `kaggle`, `neonctl`, `pnpm`, `node`, `python`, `uv`. Install what is
missing. When a step truly needs the owner (sign-up, captcha, web console), write exact
click-by-click steps in `docs/OWNER_TODO.md`, tell the owner once, and continue elsewhere.

## Code style

- Small single-purpose modules. Readable names over clever code.
- A short comment on every function and on non-obvious steps, explaining why.
- Tests for each module. Never weaken or delete a test to make it pass.
- Vercel Hobby has a daily deployment cap: batch web changes, deploy once per slice.

## Honest ML

- Split train/validation/test by store or source so near-duplicates cannot leak.
- Tune on validation only. Report test once, and say so.
- Every number in the README comes from a committed report in `docs/reports/`
  with the exact command that produced it.
- Show failure cases, not only successes.

## Product tone

- Calm, functional dashboard. Real empty, loading and error states. Responsive.
- English default with a Bangla toggle; both must read naturally (no word-for-word Bangla).
- No gradient text, neon, glassmorphism, sparkle icons, "AI-powered" badges,
  fake testimonials, fake logos or invented metrics.
- The shipped site never talks about how it was built. Engineering evidence lives
  only in the README and `docs/`.

## Repository map

| Path | What |
| --- | --- |
| `apps/web/` | Next.js app (Vercel): capture, in-browser detection, history, chat |
| `python/` | `shelfsense` package, CLI and FastAPI app |
| `training/` | Dataset scripts, Kaggle training and evaluation (uv) |
| `scripts/` | Repo tooling: hooks logic, CI checks, `check-done.mjs` |
| `docs/` | State, decisions, data card, model card, reports |
| `.githooks/` | commit-msg, pre-commit, pre-push |

## Key documents

- `docs/PROJECT_STATE.md` what exists now
- `docs/features.json` every deliverable with status, model tag and evidence
- `docs/HANDOFF.md` the exact next step
- `docs/DECISIONS.md` short ADRs, including service terms checks with dates
- `docs/LESSONS.md` mistakes and how they were fixed
- `docs/REQUIREMENTS_LOG.md` what the owner asked for (non-sensitive)
- `docs/OWNER_TODO.md` steps only the owner can do
- `docs/DATA.md` data card, `docs/MODEL_CARD.md` model card
