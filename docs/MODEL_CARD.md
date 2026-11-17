# Model Card — ShelfSense YOLOX-S INT8 Dense Shelf Detector (S3-05)

- **Last updated:** 2026-11-17
- **Model ID:** `shelfsense-yolox-s-int8.onnx` (`improved-yolox-s-v2`)
- **Architecture:** YOLOX-S (anchor-free FPN+PAN with decoupled classification, box regression, and IoU-aware objectness heads), exported to static ONNX opset 17 and quantized to dynamic INT8 (`DequantizeLinear`).
- **Task:** Single-class retail shelf product detection (`class_id = 0`, label `item`) for automated item counting, horizontal row clustering, empty-gap detection, and low-stock alerting.

---

## 1. Intended Use & Scope

- **Primary use:** Counting packaged grocery and supermarket shelf items from front-facing mobile or handheld photos, identifying horizontal empty shelf gaps along product rows, and triggering restock alerts when a shelf falls below its configured threshold.
- **Deployment target:** Runs directly in the user's browser via `onnxruntime-web` (WASM SIMD / WebGPU) and in batch CLI / FastAPI workflows via Python `onnxruntime`.
- **Out-of-scope uses:** Fine-grained brand/SKU recognition, barcode reading, price-tag OCR, or people/checkout tracking.

---

## 2. Training & Evaluation Data

- **Dataset:** Supermarket Shelves Dataset (*Humans in the Loop*, Kaggle `humansintheloop/supermarket-shelves-dataset`, 45 high-resolution images, 11,743 total boxes filtered to `Product` items; `Price` tags excluded).
- **Split protocol:** 27 train / 9 validation / 9 test, partitioned with a 64-bit perceptual difference hash (`dHash`, Hamming distance threshold $\le 8$) verifying **0 cross-split near-duplicate leaks**.
- **Tuning discipline:** All hyperparameters (input size $416 \to 640$, IoU loss weight $3.0 \to 5.0$, NMS IoU $0.45$, confidence threshold $0.25$) were tuned strictly on the 9-image validation split (`docs/reports/training-runs-s2.md`). The 9-image test split was evaluated once (`docs/reports/test-evaluation-s3.md`).

---

## 3. Measured Performance (Held-Out Test Split Reported Once)

| Split / Subset | Images | mAP@0.50 | Count MAE (items) | Count MAPE (%) | Source Report |
| --- | --- | --- | --- | --- | --- |
| Validation (`baseline-yolox-nano-v1`, INT8, $416 \times 416$) | 9 | 0.7020 | 52.11 | 22.28% | [training-runs-s2.md](reports/training-runs-s2.md) |
| Validation (`improved-yolox-s-v2`, INT8, $640 \times 640$) | 9 | **0.8317** | **29.56** | **11.18%** | [training-runs-s2.md](reports/training-runs-s2.md) |
| **Test — Overall (`improved-yolox-s-v2`, INT8, reported once)** | **9** | **0.8317** | **31.22** | **12.69%** | [test-evaluation-s3.md](reports/test-evaluation-s3.md) |
| Test — Medium density ($50 - 150$ items/shelf) | 4 | **0.9010** | **4.75** | **7.08%** | [test-evaluation-s3.md](reports/test-evaluation-s3.md) |
| Test — Dense ($> 150$ items/shelf, up to 690 items) | 5 | **0.8218** | **52.40** | **17.18%** | [test-evaluation-s3.md](reports/test-evaluation-s3.md) |

---

## 4. Artifact Size, Checksums & Latency

| File | Precision | Size | SHA-256 | Mean ONNX Run | End-to-End Scan |
| --- | --- | --- | --- | --- | --- |
| `shelfsense-yolox-s-fp32.onnx` | FP32 | 1,188,105 B (1.16 MB) | `ae8075f6658a53820c100a1e61ae2c86b2f949db88a6f5e24b8a700963d414fb` | 0.36 ms | 24.1 ms |
| `shelfsense-yolox-s-int8.onnx` | INT8 | **401,770 B (392.4 KB)** | `00deb886d46efc4a0a38d55232297d2aa81d66fd0681013377b1ccf1f353ed1c` | **0.26 ms** | **19.2 ms** |

---

## 5. Known Limitations & Failure Modes

1. **Deeply recessed shadows (`041.jpg`, 33.47% error):** Items pushed back into dark shelf recesses or thin stacked pouches viewed edge-on lose contrast and are under-counted.
2. **Extreme aisle perspective & crowding (`016.jpg`, 17.45% error):** On multi-bay photos with $>300$ items taken at an oblique angle, adjacent far-edge boxes overlap heavily and can be merged by greedy NMS.
3. **Specular glare (`005.jpg`, 13.94% error):** Direct overhead fluorescent reflections on glossy film or glass cooler doors reduce detection confidence.
4. **Depth stacking:** A single 2D photo only sees the front-facing row ("facings"); items stacked behind the front facing are not visible to the camera.

---

## 6. Licence

- **Detector architecture & training code:** Apache-2.0 / MIT (`docs/DECISIONS.md` ADR-007, ADR-010).
- **Published weights (`shelfsense-yolox-s-int8.onnx`):** Trained on the CC0 1.0 Supermarket Shelves dataset (`docs/DATA.md`), so the published weights carry **CC0 1.0 / MIT permissive terms** with no copyleft or non-commercial taint.
