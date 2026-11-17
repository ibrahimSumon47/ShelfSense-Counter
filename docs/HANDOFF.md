# Handoff

Last updated: 2026-11-17, end of Audit Fix **STEP 1** (honesty reset).

## Exact next step: STEP 2 (Real Training on Kaggle GPU)

**Recommended model tag:** `[MODEL: Claude Sonnet 5.5, MID]`

1. **STEP 2 — Real detector & GPU training (`S2-02..S2-07`, `S3-01..S3-05`):**
   - Use a real detector from a real framework (preferred: official YOLOX, Apache-2.0,
     trained from COCO-pretrained weights; if installation fails twice, use Ultralytics
     YOLO and state the AGPL-3.0 licence plainly in `README.md` and `docs/MODEL_CARD.md`;
     never write a custom fake model).
   - Train on a 2,000–4,000 image subset of the **SKU-110K** train split plus the train
     split of the 45-image CC0 **Supermarket Shelves** dataset; validate on the validation
     splits; keep the 9-image CC0 test split and the SKU-110K test split untouched until
     the final evaluation.
   - Run on the Kaggle free GPU via the `kaggle` CLI (`enable_gpu: true`, `enable_internet: true`),
     poll with a timeout, download the outputs, and commit the real kernel URL, runtime,
     GPU type, epochs, and loss curve in `docs/reports/`.
   - Evaluate saved real predictions with `pycocotools` (`AP50` and `AP50:95` with
     `maxDets >= 1000`), count MAE and MAPE, density buckets, and bootstrap 95% confidence
     intervals on both the 9-image CC0 test split and SKU-110K test split.
   - Add negative-control tests (randomly initialised model scores near-zero mAP; shuffled
     predictions score near-zero; exported ONNX has $> 1\text{M}$ parameters and plausible
     size; real CPU/browser latency measured honestly in tens to hundreds of milliseconds).
   - Export ONNX, quantize to INT8 only if the measured accuracy drop is acceptable, and
     publish the real weights to a GitHub Release with SHA-256.
2. **STEP 3 — Product (`S4-05`, `S7-01`, `S7-02`):** Wire the real ONNX model into
   `apps/web/` (`onnxruntime-web`), verify on production with Playwright using 3 real shelf
   photos and 1 non-shelf photo (near-zero detections), and confirm the web UI count matches
   the Python CLI count on the same photo.
3. **STEP 4 — Chat (`S5-02`, `S5-03`):** Re-run the 30-question bilingual evaluation against
   the real free LLM and report the true pass rate.
4. **STEP 5 — Docs & Gate (`S8-01`):** Update `scripts/check-done.mjs` to verify real
   model evidence and add a guard test forbidding `simulate_*` in reported metrics.
