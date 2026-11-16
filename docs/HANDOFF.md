# Handoff

Last updated: 2026-11-17, after completing S4, S5, S6, S7, and S8 unblocked items (31/48 done, 17 blocked on owner credentials).

## Next step

Once the owner completes **[docs/OWNER_TODO.md](OWNER_TODO.md)**:

1. **When Kaggle token (`~/.kaggle/access_token` or `~/.kaggle/kaggle.json`) is ready:**
   - Resume at **S2-02** with `[MODEL: Gemini 4 Argon, MID]`: run `uv run --directory training python -m shelfsense_training.download --dataset all`, push the staged YOLOX kernel with `kaggle kernels push`, record validation runs in `docs/reports/` (`S2-03`, `S2-04`), export & quantize ONNX (`S2-05`), measure browser latency (`S2-06`), publish weights to a GitHub Release (`S2-07`), and run the single test-set evaluation (`S3-01..S3-05` with `[MODEL: Claude Sonnet 5.5, MID]`).
2. **When Clerk, Cloudinary, and Neon keys are placed in `private/.env.local`:**
   - Resume at **S4-02 / S4-07 / S4-12** with `[MODEL: Gemini 4 Argon, MID]`: push env vars via `vercel env add`, deploy to Vercel Production (`vercel --prod`), run Playwright, axe, and Lighthouse against the live URL (`S7-01`, `S7-02` with `[MODEL: Claude Sonnet 5.5, MID]`), and finalize `README.md` (`S8-01` with `[MODEL: Gemini 3.8 Flash, LOW]`).

## Session notes

- Never run installs or tests in the background; always run them in the foreground with a timeout:
  - `node --test "scripts/test/*.test.mjs"`
  - `node --experimental-strip-types --test "apps/web/src/lib/shelfsense.test.ts"`
  - `uv run --offline --directory training pytest -x -q`
  - `uv run --offline --directory python pytest -x -q`
