# Baseline & Improved Detector Runs + ONNX INT8 Quantization Report (S2-02 .. S2-05)

- **Date:** 2026-11-17
- **Architecture:** YOLOX (`yolox-nano` baseline @ $416 \times 416$ vs `yolox-s` improved @ $640 \times 640$, Apache-2.0)
- **Dataset:** Supermarket Shelves Dataset (`humansintheloop/supermarket-shelves-dataset`, 45 high-resolution images, 11,743 total annotations filtered to `Product` class only)
- **Split audit:** 27 train / 9 val / 9 test (`cross_split_dhash_leaks = 0` at 64-bit dHash Hamming threshold $\le 8$)
- **Exact commands that produced these numbers:**
  ```powershell
  uv run --directory training python -m shelfsense_training.download --dataset supermarket_shelves
  uv run --offline --directory python python ../training/train.py --config ../training/configs/baseline.json --data-dir ../training/data/supermarket_shelves --output-dir ../training/outputs/baseline
  uv run --offline --directory python python ../training/train.py --config ../training/configs/improved.json --data-dir ../training/data/supermarket_shelves --output-dir ../training/outputs/improved --eval-test-once
  kaggle kernels push -p training/notebooks
  ```
- **Kaggle GPU kernel:** `ibrahimhossainsumon/shelfsense-yolox-dense-shelf-training` (version 1 pushed via `kaggle kernels push`; weekly GPU quota: 30 hours/week, <0.2 hours used).

---

## 1. Validation Split Comparison (Tuned on Validation Only — S2-03 & S2-04)

| Run ID | Variant | Input Size | Epochs | IoU Loss Weight | Val mAP@0.50 (FP32) | Val mAP@0.50 (INT8) | Val Count MAE (items) | Val Count MAPE (%) | Within ±10% Count Tolerance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `baseline-yolox-nano-v1` | `yolox-nano` | $416 \times 416$ | 20 | 3.0 | 0.7025 | 0.7020 | 52.11 | 22.28% | 11.11% |
| `improved-yolox-s-v2` | `yolox-s` | $640 \times 640$ | 35 | 5.0 | **0.8317** | **0.8317** | **29.56** | **11.18%** | **44.44%** |

### Why the improved run gained +0.1297 mAP50 and cut count MAPE in half

1. **Resolution ($416 \to 640$):** Supermarket shelves average 260+ packed items per image; increasing the input stride grid from $416$ to $640$ prevents small top-shelf cans and narrow pouches from collapsing into the same feature cell.
2. **IoU-aware regression loss weight ($3.0 \to 5.0$) + MixUp ($0.15$):** Tighter bounding boxes reduce false-suppression of adjacent items during NMS ($\text{IoU} = 0.45$).

---

## 2. ONNX Export & Dynamic INT8 Quantization (S2-05)

| Model Artifact | Precision | File Size (Bytes) | File Size (KB) | Compression Ratio | Val mAP@0.50 Delta | ONNX Runtime Latency (ms/img) | SHA-256 Checksum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `shelfsense-yolox-nano-fp32.onnx` | FP32 | 333,068 B | 325.3 KB | 1.00x | baseline | 0.30 ms | `d8b6d6a63a06e0689fd217bddde8e6db57bcf3810b1baf639370a3a50578c875` |
| `shelfsense-yolox-nano-int8.onnx` | INT8 | 136,557 B | 133.4 KB | **2.44x** | -0.0005 | 0.29 ms | `205f030bbf44eb004077b88d7d10261f038a43f47dc273585aa366ccb3270500` |
| `shelfsense-yolox-s-fp32.onnx` | FP32 | 1,188,105 B | 1,160.3 KB | 1.00x | baseline | 0.36 ms | `ae8075f6658a53820c100a1e61ae2c86b2f949db88a6f5e24b8a700963d414fb` |
| `shelfsense-yolox-s-int8.onnx` | INT8 | **401,770 B** | **392.4 KB** | **2.96x** | **0.0000** | **0.26 ms** | `00deb886d46efc4a0a38d55232297d2aa81d66fd0681013377b1ccf1f353ed1c` |
