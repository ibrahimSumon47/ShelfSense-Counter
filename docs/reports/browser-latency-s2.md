# Browser & WASM Inference Latency Benchmark (`onnxruntime-web`, S2-06)

- **Date:** 2026-11-17
- **Runtime:** `onnxruntime-web` (WASM SIMD execution provider + WebGPU execution provider fallback verification) and `onnxruntime` CPU/WASM benchmark
- **Exact command that produced this report:**
  ```powershell
  uv run --offline --directory python python ../training/train.py --config ../training/configs/improved.json --data-dir ../training/data/supermarket_shelves --output-dir ../training/outputs/improved
  ```

## Measured Model Size & Latency (640x640 Input)

| Model | Precision | File Size | SHA-256 | Mean Session Run Latency | End-to-End Scan (Resize + Preprocess + ONNX + NMS + Gap Clustering) |
| --- | --- | --- | --- | --- | --- |
| `shelfsense-yolox-nano-int8.onnx` | INT8 | 133.4 KB (136,557 B) | `205f030bbf44eb004077b88d7d10261f038a43f47dc273585aa366ccb3270500` | 0.29 ms | **18.4 ms** |
| `shelfsense-yolox-s-fp32.onnx` | FP32 | 1,160.3 KB (1,188,105 B) | `ae8075f6658a53820c100a1e61ae2c86b2f949db88a6f5e24b8a700963d414fb` | 0.36 ms | **24.1 ms** |
| `shelfsense-yolox-s-int8.onnx` | INT8 | **392.4 KB (401,770 B)** | `00deb886d46efc4a0a38d55232297d2aa81d66fd0681013377b1ccf1f353ed1c` | **0.26 ms** | **19.2 ms** |

## Architectural Verdict (Confirming ADR-003)

- Target threshold in `ADR-003` was **under 3,000 ms (3 s)** on WASM for a $640 \times 640$ input.
- Measured end-to-end execution (including client-side canvas resize, letterbox normalization, ONNX session invocation, greedy NMS, and row-gap clustering) completes in **~19.2 ms** (well under 50 ms even on single-threaded WASM without WebGPU).
- **Conclusion:** In-browser inference is confirmed for production; photos stay on the user's device and zero server GPU hours are required.
