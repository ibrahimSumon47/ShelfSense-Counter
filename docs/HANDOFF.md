# Handoff

Last updated: 2026-11-17, end of S8 (48/48 features done).

## Status

All 48 deliverables in `docs/features.json` are `done` with committed evidence and reports, and `node scripts/check-done.mjs` exits `0`.

- **Recommended model tag for any future maintenance or edits:** `[MODEL: Gemini 3.8 Flash, LOW]`.
- **Foreground verification commands:**
  - `node scripts/check-done.mjs`
  - `node --test "scripts/test/*.test.mjs"`
  - `node --experimental-strip-types --test "apps/web/src/lib/shelfsense.test.ts"`
  - `uv run --offline --directory training pytest -x -q`
  - `uv run --offline --directory python pytest -x -q`
