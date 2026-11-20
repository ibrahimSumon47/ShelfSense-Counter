# Handoff

Last updated: 2026-11-20 10:45 (46/48; SKU-110K validation and test measured and committed,
release and deployment done, production checks left)

## Where things stand

Kernel `ibrahimhossainsumon/shelfsense-fcos-training` version 1 finished on 2026-11-19 23:57:52
after 12,658 s on a Tesla T4 (12 epochs, best checkpoint from epoch 8). Its exported pair was
scored by `ibrahimhossainsumon/shelfsense-fcos-eval` version 1 on Kaggle CPU: 200 SKU-110K
validation images to fix the thresholds, then 200 test images once.

SKU-110K test, 29,092 items: int8 mAP50 0.8418, mAP50-95 0.4844, count MAE 26.52, MAPE 21.29 %;
fp32 mAP50 0.8418, count MAE 26.55. Validation: 0.8524 and 0.8602 mAP50, MAE 27.68 both.
The JSON, the prediction files and the rescoring recipe are in `docs/reports/test-evaluation.md`
and `docs/reports/sku110k-*.json`.

## The two traps in this pipeline

1. **Do not normalise twice.** The exporter bakes ImageNet mean/std into the graph, so
   `eval_onnx.py` must be called with `--normalise no` and `run_raw_candidates` must keep
   `normalise=False` (a test pins the default). The run's own `metrics.json` SKU numbers
   (mAP50 0.13) were produced with the old reversed default and must never be quoted.
2. **`primary` has no `onnx_file` key.** It sits on the model entry one level up. The eval
   notebook's summary cell assumed otherwise and died with `KeyError` after both splits were
   already scored and written; it is fixed, but check the log tail, not just the kernel status.

## Exact next step

1. `S7-01`: run the Playwright flows against https://shelfsense-counter.vercel.app - page loads in
   both themes and languages, upload of a committed CC0 test image produces a count and boxes,
   CSV export and save-scan behave, and the chat refuses without stored data. Record the command,
   the pass/fail list and the commit under test in `docs/reports/`.
2. `S7-02`: axe-core (zero violations) and Lighthouse (mobile and desktop) against the same URL,
   with the scores, the Date/version and the exact command in the same report.
3. Then `node scripts/check-done.mjs` must exit 0. It currently reports `S7-01` next.

## Blocked elsewhere

`GOOGLE_GENERATIVE_AI_API_KEY` is in the Vercel project but cannot be read back, and
`private/.env.local` is missing on this PC, so the live-LLM chat checks cannot be re-run here.
Exact owner steps are item 2b in `docs/OWNER_TODO.md`.

## Quota

Training used one kernel run of about 3.5 h GPU time; the evaluation kernel was CPU-only. No GPU
quota was spent after that, and none is needed for the remaining items.
