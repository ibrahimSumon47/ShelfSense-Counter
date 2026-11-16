# Model card

Status: draft. Completed in S3-05 from committed reports only.

## Model

- Architecture: chosen in S2-01 (see `docs/DECISIONS.md`, ADR-006).
- Task: single-class product detection on retail shelves ("item"), used to count items
  and find empty gaps.
- Format: ONNX, int8 quantized, run in the browser with onnxruntime-web.

## Intended use

Counting packaged products on grocery and supermarket shelf photos to support restocking.

## Not intended for

Identifying specific brands or SKUs, people, or anything outside retail shelves.

## Metrics

Filled from `docs/reports/` (test split reported once): mAP50, count MAE, count
percentage error, results by shelf density.

## Limits and failure cases

Filled in S3-03 with a gallery of real failures.

## Licence

Code: MIT. Weights: follow the training data licences (see `docs/DATA.md`).
