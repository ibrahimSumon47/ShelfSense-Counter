# Handoff

Last updated: 2026-11-16, end of S2-01 + Kaggle/eval harness.

## Next step

**S4-01 Next.js app scaffold, dark blue-grey and light themes, next-intl en/bn.**
Use `[MODEL: Gemini 4 Argon, MID]`.

1. Create the pnpm workspace (`pnpm-workspace.yaml`) and `apps/web/` Next.js App Router
   application with TypeScript and Tailwind CSS.
2. Implement the dark blue-grey operations dashboard theme and light theme toggle,
   and configure bilingual `next-intl` (or typed dictionary provider) with natural English
   and Bangla (`en` / `bn`) copy.
3. Also implement the pure TypeScript modules for **S4-04** (client-side image resize),
   **S4-05** (in-browser `onnxruntime-web` detection & box overlay), **S4-06** (empty-gap
   detection from horizontal spacing within shelf rows, with unit tests), and **S4-10**
   (CSV export), or **S6-01..S6-03** (`python/` `shelfsense` package, CLI, and FastAPI app)
   which have zero external account blockers.
4. Once the owner completes `docs/OWNER_TODO.md` item 2 (Kaggle token + phone verification),
   unblock and run `S2-02..S2-07` and `S3-01..S3-05`.

## Session notes

- Run `node --test "scripts/test/*.test.mjs"` and `uv run --offline --directory training pytest`
  before every commit.
