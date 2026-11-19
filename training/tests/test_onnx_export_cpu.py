"""Exports a tiny randomly initialised FCOS to ONNX on CPU and runs it in onnxruntime.

This is the pre-flight check for the Kaggle kernel: an export bug costs a whole GPU slot,
so CI builds the real wrapper at 128 px (a multiple of 128, so every FPN stride is exact)
and verifies the graph shape, the score range and that the output depends on the input.
Skipped when torch, onnx or onnxruntime are not installed.
"""
import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("onnx")
ort = pytest.importorskip("onnxruntime")

from shelfsense_training.export import export_fcos_onnx  # noqa: E402


def test_export_tiny_fcos_runs_on_cpu(tmp_path) -> None:
    """The exported graph runs on CPU, keeps every candidate and reacts to the image."""
    from torchvision.models.detection import fcos_resnet50_fpn

    torch.manual_seed(0)
    model = fcos_resnet50_fpn(
        weights=None,
        weights_backbone=None,
        num_classes=2,
        min_size=128,
        max_size=128,
        detections_per_img=1000,
        topk_candidates=1500,
    )
    target = tmp_path / "tiny-fcos.onnx"
    info = export_fcos_onnx(model.eval(), target, input_size=128)

    assert target.is_file()
    assert info["normalisation"].startswith("in graph")
    session = ort.InferenceSession(str(target), providers=["CPUExecutionProvider"])
    name = session.get_inputs()[0].name

    zeros = session.run(None, {name: np.zeros((1, 3, 128, 128), dtype=np.float32)})[0]
    noise = session.run(None, {name: np.random.default_rng(0).uniform(0, 1, (1, 3, 128, 128)).astype(np.float32)})[0]

    # 16^2 + 8^2 + 4^2 + 2^2 + 1^2 locations at strides 8..128, one anchor each.
    assert zeros.shape == (1, 341, 6)
    assert np.all(zeros[0, :, 4] >= 0.0) and np.all(zeros[0, :, 4] <= 1.0)
    assert float(np.abs(zeros - noise).max()) > 1e-4
