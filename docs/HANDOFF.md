# Handoff

Last updated: 2026-11-17 (33/48 features done; real training kernel v2 queued on Kaggle GPU).

## Exact next step

**Recommended model tag:** `[MODEL: Claude Sonnet 5.5, MID]`

1. **Poll / retrieve the Kaggle GPU training run (`S2-02..S2-07`, `S3-01..S3-05`):**
   - Check status:
     ```powershell
     kaggle kernels status ibrahimhossainsumon/shelfsense-yolox-dense-shelf-training
     ```
   - Currently `KernelWorkerStatus.QUEUED` on Kaggle's free GPU worker pool.
   - **If Kaggle completes:** download outputs into `training/outputs/` (gitignored):
     ```powershell
     kaggle kernels output ibrahimhossainsumon/shelfsense-yolox-dense-shelf-training -p training/outputs
     ```
   - **If Kaggle's free GPU queue stays backed up or quota is exhausted (Colab Pro fallback):**
     1. Open https://colab.research.google.com → **File → Upload notebook** → select
        `training/notebooks/colab_train.ipynb`.
     2. Choose **Runtime → Change runtime type → T4 GPU (or A100)**, upload `~/.kaggle/access_token`
        or `~/.kaggle/kaggle.json` to `/root/.kaggle/`, and run the cells.
     3. Download `/content/outputs/baseline/` and `/content/outputs/improved/` from Colab
        into `E:\AI Engineering Projects\ShelfSense-Counter\training\outputs\` (gitignored).
   - Once `training/outputs/baseline/metrics.json` and `training/outputs/improved/metrics.json`
     and the `.onnx` weights (`> 1M` parameters, verified by `verify_onnx_model_plausibility`)
     are in `training/outputs/`:
     - Commit the real training logs, loss curves, and `pycocotools` (`maxDets=1000`) +
       bootstrap 95% CI reports in `docs/reports/`.
     - Publish the real `.onnx` weights to a GitHub Release (`gh release create v0.2.0 ...`)
       with SHA-256 checksums (`S2-07`).
2. **STEP 3 — Wire real ONNX model into `apps/web/` & verify on production (`S4-05`, `S7-01`, `S7-02`):**
   - Flip `MODEL_AVAILABLE = true` in `apps/web/src/app/page.tsx` and load the real ONNX
     model with `onnxruntime-web`.
   - Verify with Playwright on production using 3 different real shelf photos and 1
     non-shelf photo (must give near-zero detections), and confirm the web UI count matches
     `shelfsense count photo.jpg --model ...` on the same photo.
3. **STEP 5 — Finalize `README.md` & `docs/MODEL_CARD.md` (`S8-01`, `S3-05`)** with the
   real measured numbers so `node scripts/check-done.mjs` exits `0`.
