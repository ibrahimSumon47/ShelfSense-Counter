# Handoff

Last updated: 2026-11-16, end of S1.

## Next step

**S2-01 Detector choice with licence comparison (ADR).** Use `[MODEL: Claude Opus 5.5, HIGH]`.

1. Compare permissive object detectors suitable for dense retail shelves and browser ONNX
   execution (e.g. YOLOX Apache-2.0, RT-DETR / D-FINE Apache-2.0, vs Ultralytics AGPL-3.0)
   on architecture, anchor-free/query capacity for 150–300 items per shelf, ONNX opset
   compatibility with `onnxruntime-web`, and licensing. Record ADR-010 in `docs/DECISIONS.md`.
2. Proceed to **S2-02** (`[MODEL: Gemini 4 Argon, MID]`): build the Kaggle training script/kernel
   metadata (`kernel-metadata.json`), ONNX export + int8 quantization script (S2-05), and local
   smoke training/export tests. If the owner's Kaggle token (`~/.kaggle/access_token` or
   `kaggle.json`) is present, push and launch the Kaggle GPU run via `kaggle kernels push`;
   if still waiting on `OWNER_TODO.md` item 2, keep `S2-02`/`S2-03`/`S2-04` marked `blocked` or
   `in_progress` and continue with unblocked slices (e.g. S4 web app or S6 Python package).

## Session notes

- Run `node --test "scripts/test/*.test.mjs"` and `uv run --offline --directory training pytest`
  before every commit.
