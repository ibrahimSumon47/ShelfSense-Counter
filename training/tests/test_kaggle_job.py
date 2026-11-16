"""Unit tests for Kaggle kernel staging, metadata generation, and SHA-256 verification."""
import json
from pathlib import Path
import pytest

from shelfsense_training.kaggle_job import (
    TrainingConfig,
    build_kaggle_push_cmd,
    build_kaggle_status_cmd,
    build_kernel_metadata,
    push_kaggle_kernel,
    sha256_file,
    stage_kaggle_kernel,
)


def test_build_kernel_metadata_has_required_kaggle_fields() -> None:
    """Kaggle CLI requires id, title, code_file, language, kernel_type, and dataset_sources."""
    meta = build_kernel_metadata(
        owner="ibrahimsumon",
        kernel_slug="shelfsense-yolox-baseline",
        title="ShelfSense Baseline",
    )
    assert meta["id"] == "ibrahimsumon/shelfsense-yolox-baseline"
    assert meta["enable_gpu"] == "true"
    assert "thedatasith/sku110k-annotations" in meta["dataset_sources"]
    assert "humansintheloop/supermarket-shelves-dataset" in meta["dataset_sources"]


def test_stage_and_push_kaggle_kernel(tmp_path: Path) -> None:
    """Staging writes kernel-metadata.json, run_config.json, and train_shelfsense.py."""
    cfg = TrainingConfig(run_id="baseline-v1", variant="yolox-nano", epochs=30)
    meta_path = stage_kaggle_kernel(tmp_path, owner="ibrahimsumon", config=cfg)
    assert meta_path.is_file()
    assert (tmp_path / "run_config.json").is_file()
    assert (tmp_path / "train_shelfsense.py").is_file()

    loaded_cfg = json.loads((tmp_path / "run_config.json").read_text(encoding="utf-8"))
    assert loaded_cfg["variant"] == "yolox-nano"
    assert loaded_cfg["input_size"] == 640

    recorded: list[list[str]] = []
    push_kaggle_kernel(tmp_path, runner=lambda cmd: (recorded.append(cmd), 0)[1])
    assert recorded == [build_kaggle_push_cmd(tmp_path)]


def test_status_cmd_and_sha256(tmp_path: Path) -> None:
    """Status command validates kernel_id format and sha256_file hashes deterministically."""
    assert build_kaggle_status_cmd("owner/slug") == ["kaggle", "kernels", "status", "owner/slug"]
    with pytest.raises(ValueError, match="kernel_id"):
        build_kaggle_status_cmd("invalid")

    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"shelfsense-onnx-test")
    assert len(sha256_file(sample)) == 64
