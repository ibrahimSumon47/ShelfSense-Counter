# Handoff

Last updated: 2026-11-17, end of S6.

## Next step

**S4-01 Next.js app scaffold, dark blue-grey and light themes, next-intl en/bn.**
Use `[MODEL: Gemini 4 Argon, MID]`.

1. Create `pnpm-workspace.yaml` and `apps/web/` (Next.js App Router with TypeScript and
   Tailwind CSS).
2. Implement the dark blue-grey operations dashboard theme and light theme toggle, plus
   natural English (`en`) and Bangla (`bn`) language support.
3. Build the core S4 and S5 modules (`apps/web/src/lib/`):
   - S4-03 Drizzle Postgres schema (`stores`, `aisles`, `shelves`, `scans`, `thresholds`).
   - S4-04 client-side image resize + upload validation.
   - S4-05 in-browser `onnxruntime-web` detector and box/gap overlay.
   - S4-06 TypeScript empty-gap detection from spacing between items, with unit tests.
   - S4-08, S4-09, S4-10, S4-11 dashboard UI, trend charts, low-stock threshold alerts,
     CSV export, and responsive empty/loading/error states.
   - S5-01..S5-03 typed user-scoped database tools, bilingual chat with numeric-grounding
     verification, and the 30-question evaluation benchmark (15 EN, 15 BN).

## Session notes

- Never run installs or tests in the background; run them in the foreground with a timeout
  (`pytest -x -q`, `node --test "scripts/test/*.test.mjs"`).
