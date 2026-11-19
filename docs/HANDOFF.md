# Handoff

Last updated: 2026-11-19 23:00 (37/48 features done; FCOS run still training after 9 h 49 min on Kaggle)

**Recommended model tag:** `[MODEL: Claude Sonnet 5.5, MID]`

## Observed so far

The kernel started at 13:11 and was still `RUNNING` at 23:00, so it has passed the 9-hour mark.
Committed Kaggle notebook runs are allowed 12 hours, which puts the hard stop at about 01:11.
`plan_epochs()` deliberately clamps to the configured `min_epochs` of 12 even when the 3-hour GPU
budget says fewer (`training/tests/test_train_plan.py` pins that behaviour), and each epoch is
taking roughly 35 minutes at 800 px on the free GPU, so 12 epochs alone is about 7 hours plus the
validation sweep, the export and the single test pass.

A watch loop polling every 4 minutes logs to `/tmp/kwatch2.txt` and, the moment Kaggle reports a
terminal status, runs `kaggle kernels output ibrahimhossainsumon/shelfsense-fcos-training -p
training/outputs/fcos-v3` and appends `DOWNLOAD_EXIT=` plus the file list to the same log. Check
there first; if the loop is gone, run that download command by hand.

## Where the run stands

Kernel `ibrahimhossainsumon/shelfsense-fcos-training`, version 1, trains 12 epochs on 6,036
SKU-110K + CC0 images and writes `metrics.json`, checkpoints, ONNX files and test predictions to
`/kaggle/working/outputs`. It clones `main` at start-up, so a failure can be fixed by pushing a
commit and pushing the kernel again.

## Exact next step

1. Verify the download: `training/outputs/fcos-v3/train.log` must end with `SUCCESS`, and
   `training/outputs/fcos-v3/outputs/` must hold `metrics.json`, `checkpoints/best.pt`,
   `*-fp32.onnx`, `*-int8.onnx`, `predictions/*.json.gz`, with no `*-error.txt`. A COMPLETE
   status alone proves nothing.
2. If it FAILED: read `train.log` for the first traceback, fix `training/`, push to `main` (the
   notebook clones the repo), push the kernel again. At most 3 attempts, then record the cause
   here and in `docs/OWNER_TODO.md`.
3. With a good run, in one slice:
   - copy the test prediction files into `docs/reports/predictions/`;
   - `python training/eval_onnx.py --onnx training/outputs/fcos-v3/outputs/*-int8.onnx <and fp32>
     --dataset cc0 --split test --input-size 640 --normalise no --center-fix none
     --score-thresh <tuned> --nms-thresh <tuned> --max-dets 1000 --out docs/reports/test-evaluation.json
     --predictions-dir docs/reports/predictions` (the new export normalises in the graph, so
     `--normalise no`);
   - write `docs/reports/test-evaluation.md` with mAP50, mAP50-95, count MAE/MAPE, bootstrap 95 %
     intervals, density buckets, the worst images, the sentence that nine CC0 test images give a
     wide interval, and the FP32-versus-INT8 decision from the measured drop;
   - `python training/render_failures.py` for the failure gallery (CC0 test images, CC0 licence);
   - the count/mAP regression bundle, which needs the SKU-110K test images to reach 20 rows:
     `python training/make_regression_fixtures.py --predictions <new gz> --evaluation <new eval json>
     --cc0-test-dir training/data/supermarket_shelves --sku-test-dir <SKU110K_fixed>
     --out-dir training/fixtures` then upload `training/fixtures/shelfsense-regression-v1.tar.gz`
     to the release;
   - `gh release create v1.0.0` with the chosen ONNX file(s), `sha256sums.txt` and the fixture
     bundle from `python training/make_regression_fixtures.py`;
   - copy the chosen file into `apps/web/public/models/`, update `manifest.json`
     (`webgpu_capable` true only if the file is not dynamically quantised), deploy with
     `vercel --prod` from `apps/web`;
   - re-measure the browser on the live URL with three test-split photos and one non-shelf photo,
     run axe-core and Lighthouse, and record everything in `docs/reports/`.
4. Close: README, MODEL_CARD, DATA, DECISIONS, PROJECT_STATE, features.json, then
   `node scripts/check-done.mjs` must exit 0.

## Blocked elsewhere

`GOOGLE_GENERATIVE_AI_API_KEY` is in the Vercel project but cannot be read back, and
`private/.env.local` is missing on this PC, so the live-LLM chat checks cannot be re-run here.
Exact owner steps are item 2b in `docs/OWNER_TODO.md`.

## Quota

The first kernel used about 0.3 h of the weekly GPU quota; this run is budgeted at 3 h and writes
its own plan into `timings.planned_epochs_reason` in `metrics.json`. Record the hours in the run
report. One improvement round is allowed only if the quota clearly remains.
