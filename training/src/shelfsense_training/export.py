"""ONNX export of the trained FCOS detector, with the normalisation and the anchor
geometry baked into the graph.

Two bugs in the first exports are fixed here, both found by re-evaluating the stored
ONNX files on the CC0 validation split (docs/reports/validation-detection-cap.md):

1. The wrapper called the backbone directly, so torchvision's `GeneralizedRCNNTransform`
   never ran and the ImageNet mean/std normalisation was missing from the graph.
2. Anchor centres were decoded as (g + 0.5) * stride. torchvision's `AnchorGenerator`
   places them at g * stride and `BoxLinearCoder` scales the regression distances by the
   full anchor size, so every box was shifted half a cell down and right.

The exported tensor is `[1, N, 6] = [xc, yc, w, h, score, 1]` in input-pixel coordinates.
Thresholding, NMS and the detection cap stay in code (numpy here, onnxruntime-web in the
browser) so the cap can be raised above torchvision's default of 100.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path


def onnx_sha256(path: Path) -> str:
    """SHA-256 of a file, used in the model card and the release notes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export_fcos_onnx(model, onnx_path: Path, input_size: int, opset: int = 17) -> dict:
    """Exports backbone + FPN + head with normalisation and anchor decoding inside the graph."""
    import torch
    import torch.nn as nn

    from shelfsense_training.metrics import verify_onnx_model_plausibility

    class FCOSOnnxWrapper(nn.Module):
        """Turns [0, 1] RGB tensors into dense candidate boxes for one image."""

        def __init__(self, fcos_model: nn.Module, size: int) -> None:
            super().__init__()
            self.backbone = fcos_model.backbone
            self.head = fcos_model.head
            self.size = size
            # Copied from the model's own transform so the graph normalises exactly like training.
            mean = getattr(fcos_model.transform, "image_mean", [0.485, 0.456, 0.406])
            std = getattr(fcos_model.transform, "image_std", [0.229, 0.224, 0.225])
            self.register_buffer("mean", torch.tensor(mean, dtype=torch.float32).view(1, 3, 1, 1))
            self.register_buffer("std", torch.tensor(std, dtype=torch.float32).view(1, 3, 1, 1))

        def forward(self, images: torch.Tensor) -> torch.Tensor:
            features = self.backbone((images - self.mean) / self.std)
            feat_list = [features] if isinstance(features, torch.Tensor) else list(features.values())
            head_out = self.head(feat_list)
            cls_logits = head_out["cls_logits"]
            bbox_reg = head_out["bbox_regression"]
            ctr_logits = head_out["bbox_ctrness"]

            decoded = []
            offset = 0
            for feat in feat_list:
                _, _, fh, fw = feat.shape
                n_level = fh * fw
                # Stride of this pyramid level; the regression head predicts distances
                # normalised by this stride (BoxLinearCoder with normalize_by_size=True).
                stride = float(self.size) / float(fh)
                reg = bbox_reg[:, offset : offset + n_level, :] * stride
                cls = torch.sigmoid(cls_logits[:, offset : offset + n_level, 1:2])
                ctr = torch.sigmoid(ctr_logits[:, offset : offset + n_level, :])
                score = torch.sqrt(cls * ctr)

                gy, gx = torch.meshgrid(
                    torch.arange(fh, device=images.device, dtype=torch.float32),
                    torch.arange(fw, device=images.device, dtype=torch.float32),
                    indexing="ij",
                )
                # Anchor centres are g * stride: AnchorGenerator shifts zero-centred anchors
                # by arange(grid) * stride, with no half-cell offset.
                cx = (gx.reshape(-1) * stride).unsqueeze(0)
                cy = (gy.reshape(-1) * stride).unsqueeze(0)
                x1, y1 = cx - reg[:, :, 0], cy - reg[:, :, 1]
                x2, y2 = cx + reg[:, :, 2], cy + reg[:, :, 3]
                bw = (x2 - x1).clamp(min=1.0).unsqueeze(-1)
                bh = (y2 - y1).clamp(min=1.0).unsqueeze(-1)
                decoded.append(
                    torch.cat(
                        [
                            ((x1 + x2) * 0.5).unsqueeze(-1),
                            ((y1 + y2) * 0.5).unsqueeze(-1),
                            bw,
                            bh,
                            score,
                            torch.ones_like(score),
                        ],
                        dim=-1,
                    )
                )
                offset += n_level
            return torch.cat(decoded, dim=1)

    wrapper = FCOSOnnxWrapper(model.eval(), input_size).to("cpu").eval()
    dummy = torch.zeros((1, 3, input_size, input_size), dtype=torch.float32)
    torch.onnx.export(
        wrapper,
        dummy,
        str(onnx_path),
        input_names=["images"],
        output_names=["output"],
        opset_version=opset,
        do_constant_folding=True,
        dynamo=False,
    )
    plausibility = verify_onnx_model_plausibility(str(onnx_path))
    return {
        "path": onnx_path.name,
        "size_bytes": plausibility["size_bytes"],
        "sha256": onnx_sha256(onnx_path),
        "plausibility": plausibility,
        "input_size": input_size,
        "normalisation": "in graph (ImageNet mean/std)",
        "anchor_centres": "g * stride (torchvision convention)",
    }


def quantize_int8_dynamic(fp32_path: Path, int8_path: Path) -> dict | None:
    """Dynamic INT8 quantisation; returns size and SHA-256, or None if unsupported."""
    try:
        from onnxruntime.quantization import QuantType, quantize_dynamic

        quantize_dynamic(model_input=str(fp32_path), model_output=str(int8_path), weight_type=QuantType.QUInt8)
    except Exception as exc:  # some graphs have ops onnxruntime cannot quantise dynamically
        print(f"INT8 quantisation skipped: {exc}")
        return None
    if not int8_path.is_file():
        return None
    return {"path": int8_path.name, "size_bytes": int8_path.stat().st_size, "sha256": onnx_sha256(int8_path)}


def measure_cpu_latency(onnx_path: Path, input_size: int, runs: int = 3) -> float:
    """Median-ish CPU latency in ms for one image (warm-up run first, then `runs` timed runs)."""
    import numpy as np
    import onnxruntime as ort

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    name = session.get_inputs()[0].name
    sample = np.zeros((1, 3, input_size, input_size), dtype=np.float32)
    session.run(None, {name: sample})
    started = time.perf_counter()
    for _ in range(runs):
        session.run(None, {name: sample})
    return round((time.perf_counter() - started) / runs * 1000.0, 2)
