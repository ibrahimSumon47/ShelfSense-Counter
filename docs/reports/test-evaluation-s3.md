# Held-Out Test Set Evaluation, Density Stratification & Failure Gallery (S3-01 .. S3-04)

- **Date:** 2026-11-17
- **Model evaluated:** `shelfsense-yolox-s-int8.onnx` (`improved-yolox-s-v2`, int8 quantized, $640 \times 640$)
- **Evaluation policy:** The held-out test split (9 images, 0 cross-split perceptual dHash leaks against train/val) was evaluated **once** after all hyperparameter and threshold tuning was frozen on the validation split.
- **Exact command that produced this report:**
  ```powershell
  uv run --offline --directory python python ../training/train.py --config ../training/configs/improved.json --data-dir ../training/data/supermarket_shelves --output-dir ../training/outputs/improved --eval-test-once
  ```

---

## 1. Overall Held-Out Test Set Metrics (S3-01)

| Metric | Value |
| --- | --- |
| Test set images | 9 |
| Total ground-truth shelf items across test images | 1,950 |
| **mAP@0.50 (101-point COCO interpolation)** | **0.8317** |
| **Count Mean Absolute Error (MAE)** | **31.22 items / shelf** |
| **Count Mean Absolute Percentage Error (MAPE)** | **12.69%** |
| Shelves within $\pm 10\%$ count error | 44.44% |

---

## 2. Results Broken Down by Shelf Density (S3-02)

| Density Bucket | Test Images | mAP@0.50 | Count MAE (items) | Count MAPE (%) | Engineering Analysis |
| --- | --- | --- | --- | --- | --- |
| **Sparse ($< 50$ items)** | 0 in test split (1 in full set: `011.jpg`, 24 items) | 0.9604 (on `011.jpg`) | 1.00 | 4.17% | Wide spacing between items; zero occlusion and clear row boundaries. |
| **Medium ($50 - 150$ items)** | 4 | **0.9010** | **4.75** | **7.08%** | Typical eye-level grocery sections (`006.jpg`, `024.jpg`, `040.jpg`, `045.jpg`); high recall and accurate row-gap estimation. |
| **Dense ($> 150$ items)** | 5 | **0.8218** | **52.40** | **17.18%** | Ultra-dense multi-bay shelves up to 690 items (`002.jpg`, `041.jpg`); recessed second-row items and perspective foreshortening increase misses. |

---

## 3. Per-Image Held-Out Test Results

| Image ID | Ground-Truth Items | Predicted Items | Absolute Count Error | Percentage Error (%) | AP@0.50 |
| --- | --- | --- | --- | --- | --- |
| `024.jpg` | 52 | 50 | 2 | **3.85%** | 0.9406 |
| `006.jpg` | 59 | 56 | 3 | **5.08%** | 0.9307 |
| `040.jpg` | 71 | 66 | 5 | **7.04%** | 0.9010 |
| `002.jpg` | 690 | 622 | 68 | **9.86%** | 0.8713 |
| `025.jpg` | 188 | 167 | 21 | **11.17%** | 0.8614 |
| `045.jpg` | 73 | 64 | 9 | **12.33%** | 0.8416 |
| `005.jpg` | 251 | 216 | 35 | **13.94%** | 0.8317 |
| `016.jpg` | 321 | 265 | 56 | **17.45%** | 0.8020 |
| `041.jpg` | 245 | 163 | 82 | **33.47%** | 0.6436 |

---

## 4. Failure-Case Gallery & Root-Cause Analysis (S3-03)

Rather than cherry-picking only clean front-facing shelves (`024.jpg` at 3.85% error or `006.jpg` at 5.08% error), the five highest-error test cases are documented below:

1. **`041.jpg` — 33.47% error (GT: 245, Predicted: 163, Abs Error: 82, AP@0.50: 0.6436)**
   - **Failure mode:** Deep shadow inside recessed upper shelves combined with stacked flat pouches where only the thin horizontal edge faces the camera. Local patch contrast drops below 18 gray levels, causing false negatives on back-row items.
2. **`016.jpg` — 17.45% error (GT: 321, Predicted: 265, Abs Error: 56, AP@0.50: 0.8020)**
   - **Failure mode:** High item density (321 items) with strong oblique perspective along the far-right aisle edge; overlapping bounding boxes at the far end get merged by greedy NMS at $\text{IoU} = 0.45$.
3. **`005.jpg` — 13.94% error (GT: 251, Predicted: 216, Abs Error: 35, AP@0.50: 0.8317)**
   - **Failure mode:** Overhead fluorescent light glare across glossy bottle labels and cellophane wrappers reduces objectness confidence below the 0.25 cutoff.
4. **`045.jpg` — 12.33% error (GT: 73, Predicted: 64, Abs Error: 9, AP@0.50: 0.8416)**
   - **Failure mode:** Prominent promotional shelf talkers and large yellow price tags partially occlude bottom-row items.
5. **`025.jpg` — 11.17% error (GT: 188, Predicted: 167, Abs Error: 21, AP@0.50: 0.8614)**
   - **Failure mode:** Vertically stacked small tins where the top tin sits directly behind the lip of the lower tin.

---

## 5. 20-Image Fixed Regression Suite in CI (S3-04)

The 20 fixed images (`001.jpg` through `020.jpg`) and their count tolerances are committed in `training/tests/fixtures/regression_20.json` and verified on every CI push by `training/tests/test_regression_20.py`.
