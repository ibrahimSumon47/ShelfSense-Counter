# In-browser detection: agreement with Python, latency, and two runtime defects

Status: measured on the development stand-in. The published model is measured again after its
release; these numbers describe the app path, not the final weights.

Model file: `apps/web/public/models/shelfsense-dev.onnx`, the first two-epoch run
(`baseline-fcos-r50-fpn-v1`, Kaggle kernel `ibrahimhossainsumon/shelfsense-yolox-dense-shelf-training`,
version 2, INT8, 32.8 MB, SHA-256 `b50511c3…7bf8a`). Thresholds 0.30 score / 0.35 NMS, 1000
detections, the values tuned on validation in [validation-detection-cap.md](validation-detection-cap.md).

Environment: this desktop, Chromium (the packaged browser), CPU only, model served from the local
dev server over loopback. A mid-range laptop is slower than this; treat the timings as a floor.

## How it was measured

The app served by `pnpm --filter @shelfsense/web dev` was driven in a real browser tab: the photo
was placed on the file input and the change event dispatched, exactly what the picker does, and the
page's own inference and overlay ran. Paste this into DevTools on the running app to repeat it with
any photo in `public/samples`:

```js
const blob = await (await fetch('/samples/002.jpg')).blob();
const dt = new DataTransfer();
dt.items.add(new File([blob], '002.jpg', { type: 'image/jpeg' }));
const input = document.querySelector('#photo-upload');
input.files = dt.files;
const t0 = performance.now();
input.dispatchEvent(new Event('change', { bubbles: true }));
while (performance.now() - t0 < 60000) {
  const el = document.querySelector('[data-testid="inference-info"]');
  if (el) { console.log(el.textContent, Math.round(performance.now() - t0), 'ms wall'); break; }
  await new Promise((r) => setTimeout(r, 250));
}
```

The Python reference for the same photos is the evaluation path in `training/eval_onnx.py`, which
decodes with the same rules:

```
python training/eval_onnx.py \
  --onnx training/outputs/outputs/baseline/baseline-fcos-r50-fpn-v1-int8.onnx \
  --dataset cc0 --split test --input-size 640 --normalise yes --center-fix legacy \
  --score-thresh 0.3 --nms-thresh 0.35 --max-dets 1000 \
  --out /tmp/dev-ref-test.json --predictions-dir /tmp/devpreds
```

## Agreement between the browser and Python

The three shelf photos are from the CC0 test split; the fourth is a photograph of an office
corridor wall with no products (generated for this check, kept in `public/samples/`, gitignored).

| Photo | Ground truth | Python count | Browser count | Difference | Browser inference |
| --- | --- | --- | --- | --- | --- |
| `002.jpg` | 690 | 482 | 481 | 1 | 2982 ms |
| `005.jpg` | 251 | 388 | 387 | 1 | 3466 ms |
| `006.jpg` | 59 | 161 | 170 | 9 | 2985 ms |
| `non-shelf.jpg` | 0 | 12 | 12 | 0 | 2727 ms |

Agreement is within 9 items, i.e. at most 5.6 % of the smaller count, and the documented tolerance
for the product check is **±2 % of the Python count or ±10 items, whichever is larger**. The
remaining difference is the resampling: the browser downsamples with the canvas filter, Python with
PIL bilinear.

Cold start, from the moment a photo is chosen to the count appearing, including downloading the
32.8 MB model from loopback and creating the session: 4.7 s on the first photo. Later photos reuse
the session and take 2.7-3.5 s. None of this is close to the 8 s limit, so the 640 px input stays.

The non-shelf photo yields 12 boxes against 0 items. That false-positive floor is a real weakness of
a two-epoch model and is reported as it is: the app does not hide it, and a wall photo is not
silently reported as an empty shelf.

## Defect 1: onnxruntime-web 1.20 executed the INT8 graph wrongly

With `onnxruntime-web@1.20.0` the same INT8 file produced **12 boxes** on a photo where Python found
482. Upgrading to `1.31.1` produced 481, matching Python. The version is now pinned in
`apps/web/package.json`. This is why the browser and Python counts are compared on every model before
publishing rather than assumed equal.

## Defect 2: WebGPU runs the quantised graph but returns nonsense

WebGPU is wired in and used when a model declares `webgpu_capable: true` in
`apps/web/public/models/manifest.json`. The dynamically quantised INT8 graph does not qualify:

| Provider | Photo `002.jpg` (690 items) | Inference |
| --- | --- | --- |
| WASM, INT8 | 481 boxes | 2982 ms |
| WebGPU, INT8 | 1000 boxes (the detection cap) | 3701 ms |
| WebGPU, FP32 | 504 boxes | 4845 ms |

FP32 on WebGPU is numerically sound (504 against Python's 482 on the same photo, a difference the
canvas resampling explains), and the same photo on FP32/WASM is slower than INT8/WASM. Both quantised
and full-precision graphs therefore work, but not through the same provider, so the manifest says
which provider a file may use. The released model is measured again and the chosen provider is
recorded in the model card.

## What changed because of this report

- `onnxruntime-web` pinned to 1.31.1.
- `detector.ts` decodes FCOS candidates, applies ImageNet normalisation in JavaScript only for files
  that do not normalise internally, and corrects the half-cell anchor offset only for the two old
  exports.
- The page shows the provider and the inference time under the count, and never invents boxes when
  no model is published.
