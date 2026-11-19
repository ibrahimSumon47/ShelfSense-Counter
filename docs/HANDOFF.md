# Handoff

Last updated: 2026-11-19 (36/48 features done; FCOS run pushed to Kaggle, waiting on the GPU)

**Recommended model tag:** `[MODEL: Claude Sonnet 5.5, MID]`

## Exact next step

Poll the kernel `shelfsense-fcos-training`, at most once every 8 minutes, with the encoding set so
the CLI cannot hit a Windows charmap error:

```powershell
$env:PYTHONUTF8 = "1"
kaggle kernels status ibrahimhossainsumon/shelfsense-fcos-training
```

When it reports `KernelWorkerStatus.COMPLETE`:

```powershell
$env:PYTHONUTF8 = "1"
kaggle kernels output ibrahimhossainsumon/shelfsense-fcos-training -p training/outputs/fcos-v3
```

Then check, in this order, before trusting anything:

1. `training/outputs/fcos-v3/train.log` ends with `SUCCESS` (a COMPLETE status alone proves
   nothing; the notebook raises so a failure shows as ERROR).
2. `training/outputs/fcos-v3/outputs/metrics.json` exists and has `val_sku110k`, `val_cc0`,
   `test_sku110k_once`, `test_cc0_once`, `thresholds`, `timings` and `onnx`.
3. `checkpoints/best.pt`, `<run_id>-fp32.onnx`, `<run_id>-int8.onnx` and
   `predictions/*.json.gz` are all there.
4. No `*-error.txt` file is present.

If it FAILED, read `train.log` for the first traceback, fix the cause in `training/` (the notebook
clones `main`, so the fix must be pushed first), push and run again. At most 3 attempts, then
write the cause here and in `docs/OWNER_TODO.md` and stop attempting GPU runs this week.

## After a good run

1. Re-run `python training/eval_onnx.py` on the new files for the committed validation report,
   and copy the run's `predictions/*.json.gz` into `docs/reports/predictions/`.
2. Report the test split once in `docs/reports/test-evaluation.md` (mAP50, mAP50-95, count MAE,
   MAPE, bootstrap 95 % interval, per-density buckets, per-image worst cases, and the sentence
   that nine CC0 test images give a wide interval).
3. `gh release create` the chosen weights (never in git) with SHA-256 checksums, then `S2-07`.
4. Wire `apps/web/src/lib/detector.ts` to the released model with onnxruntime-web, measure real
   browser latency, and run the production checks (`S4-05`, `S2-06`, `S7-01`, `S7-02`).
5. Close with the README pass (`S8-01`) and `node scripts/check-done.mjs` exiting 0.

## Quota

Kaggle GPU: the first kernel version used about 0.3 h; this run is budgeted at 3 h and the plan
is written into its `metrics.json` (`timings.planned_epochs_reason`). Record hours used in the
run report. Remaining weekly quota is the only thing limiting a second improvement round.
