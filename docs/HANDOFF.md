# Handoff

Last updated: 2026-11-17 (33/48 features done; Kaggle GPU kernel v3 pushed and polled, currently `QUEUED`).

## Exact next step

**Recommended model tag:** `[MODEL: Claude Sonnet 5.5, MID]`

### Option A — Check if the Kaggle GPU run finished

Run:
```powershell
kaggle kernels status ibrahimhossainsumon/shelfsense-yolox-dense-shelf-training
```
If it prints `KernelWorkerStatus.COMPLETE`, download the real weights and `metrics.json` into `training/outputs/` (gitignored):
```powershell
kaggle kernels output ibrahimhossainsumon/shelfsense-yolox-dense-shelf-training -p training/outputs
```

### Option B — If Kaggle's free GPU queue remains backed up or weekly quota is exhausted (Colab Pro fallback)

All training, `pycocotools` (`maxDets=1000`, `AP50` and `AP50:95`), bootstrap 95% confidence interval, and ONNX export logic is portable in `training/train.py`. To run the exact same pipeline on Colab Pro:

1. Open https://colab.research.google.com → **File → Upload notebook** → upload `training/notebooks/colab_train.ipynb`.
2. In the top menu click **Runtime → Change runtime type** → select **T4 GPU** or **A100 GPU** → **Save**.
3. In a new top cell (or the Colab file pane), place your Kaggle token at `/root/.kaggle/access_token` (or `/root/.kaggle/kaggle.json` with `chmod 600`), then click **Runtime → Run all**.
4. When the cell finishes, it produces `/content/shelfsense_training_outputs.zip` containing:
   - `baseline/metrics.json` and `baseline/baseline-fcos-r50-fpn-v1-fp32.onnx` (`-int8.onnx`)
   - `improved/metrics.json` and `improved/improved-fcos-r50-fpn-v2-fp32.onnx` (`-int8.onnx`)
5. Extract `baseline/` and `improved/` into `E:\AI Engineering Projects\ShelfSense-Counter\training\outputs\` (gitignored).

### Once `training/outputs/baseline/metrics.json` and `training/outputs/improved/metrics.json` are present locally

1. **Finish Step 2 (`S2-02..S2-07`, `S3-01..S3-05`):**
   - Run `verify_onnx_model_plausibility` on the exported `.onnx` model (`> 1M` parameters, $> 4\text{ MB}$, non-constant image-dependent output).
   - Commit the real training logs, loss curves, and `pycocotools` + bootstrap 95% CI reports in `docs/reports/`.
   - Upload the real `.onnx` weights to a GitHub Release (`gh release create v0.2.0 ...`) and record the SHA-256 checksum.
2. **Finish Step 3 (`S4-05`, `S7-01`, `S7-02`):**
   - Wire the real ONNX model into `apps/web/` (`onnxruntime-web`), flip `MODEL_AVAILABLE = true`, deploy to Vercel Production, verify with Playwright on 3 real shelf photos and 1 non-shelf photo (near-zero detections), and confirm the web UI count matches `shelfsense count photo.jpg --model ...`.
3. **Finish Step 5 (`S8-01`, `S3-05`):**
   - Update `README.md` and `docs/MODEL_CARD.md` with the real measured numbers so `node scripts/check-done.mjs` exits `0`.
