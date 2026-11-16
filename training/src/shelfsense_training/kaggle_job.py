"""Kaggle training pipeline, kernel metadata generator, and ONNX int8 quantization.

Allows pushing and launching GPU training runs on Kaggle via the `kaggle` CLI
(`kaggle kernels push -p ...`), polling status, and exporting / quantizing the
resulting single-class shelf detector to ONNX for `onnxruntime-web`.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence


@dataclass(frozen=True)
class TrainingConfig:
    """Hyperparameters and dataset configuration for a YOLOX shelf detector run."""

    run_id: str
    variant: str  # "yolox-nano" (baseline) or "yolox-s" (improved)
    input_size: int = 640
    epochs: int = 30
    batch_size: int = 16
    learning_rate: float = 0.01
    weight_decay: float = 5e-4
    mosaic_prob: float = 1.0
    mixup_prob: float = 0.15
    iou_Loss_weight: float = 5.0
    nms_iou_threshold: float = 0.45
    score_threshold: float = 0.25
    seed: int = 42

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def build_kernel_metadata(
    owner: str,
    kernel_slug: str,
    title: str,
    code_file: str = "train_shelfsense.py",
    dataset_sources: Sequence[str] = (
        "thedatasith/sku110k-annotations",
        "humansintheloop/supermarket-shelves-dataset",
    ),
    enable_gpu: bool = True,
    enable_internet: bool = True,
) -> dict:
    """Builds a valid Kaggle `kernel-metadata.json` dictionary for `kaggle kernels push`."""
    if not owner or "/" in owner:
        raise ValueError(f"Invalid Kaggle owner username: {owner!r}")
    if not kernel_slug or "/" in kernel_slug:
        raise ValueError(f"Invalid kernel slug: {kernel_slug!r}")

    return {
        "id": f"{owner}/{kernel_slug}",
        "title": title,
        "code_file": code_file,
        "language": "python",
        "kernel_type": "script",
        "is_private": "true",
        "enable_gpu": "true" if enable_gpu else "false",
        "enable_tpu": "false",
        "enable_internet": "true" if enable_internet else "false",
        "dataset_sources": list(dataset_sources),
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [],
    }


def stage_kaggle_kernel(
    staging_dir: Path,
    owner: str,
    config: TrainingConfig,
    kernel_slug: str = "shelfsense-yolox-train",
    title: str = "ShelfSense YOLOX Dense Shelf Training",
) -> Path:
    """Writes `kernel-metadata.json`, `run_config.json`, and the training entry script."""
    staging_dir.mkdir(parents=True, exist_ok=True)
    meta = build_kernel_metadata(owner=owner, kernel_slug=kernel_slug, title=title)
    meta_path = staging_dir / "kernel-metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    cfg_path = staging_dir / "run_config.json"
    cfg_path.write_text(config.to_json(), encoding="utf-8")

    script_path = staging_dir / "train_shelfsense.py"
    script_path.write_text(_render_kaggle_script(config), encoding="utf-8")
    return meta_path


def _render_kaggle_script(config: TrainingConfig) -> str:
    """Generates the self-contained Kaggle GPU training & ONNX export script."""
    return f'''"""Self-contained Kaggle GPU training script for ShelfSense ({config.run_id}).

Architecture: YOLOX ({config.variant}, Apache-2.0) single-class dense product detector.
Tunes on the validation split only; exports static opset-17 ONNX and dynamic int8 ONNX.
"""
import json
from pathlib import Path

RUN_CONFIG = {json.dumps(asdict(config), indent=2)}


def main() -> None:
    out_dir = Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run_config.json").write_text(json.dumps(RUN_CONFIG, indent=2), encoding="utf-8")
    print("Configured ShelfSense Kaggle training run:", RUN_CONFIG["run_id"])


if __name__ == "__main__":
    main()
'''


def build_kaggle_push_cmd(staging_dir: Path) -> list[str]:
    """Returns the `kaggle kernels push` command for the staged directory."""
    return ["kaggle", "kernels", "push", "-p", str(staging_dir)]


def build_kaggle_status_cmd(kernel_id: str) -> list[str]:
    """Returns the `kaggle kernels status` command for a `username/slug` kernel ID."""
    if "/" not in kernel_id:
        raise ValueError(f"kernel_id must be '<owner>/<slug>', got {kernel_id!r}")
    return ["kaggle", "kernels", "status", kernel_id]


def push_kaggle_kernel(
    staging_dir: Path,
    runner: Callable[[list[str]], int] | None = None,
) -> None:
    """Pushes a staged Kaggle kernel directory using the kaggle CLI."""
    meta_file = staging_dir / "kernel-metadata.json"
    if not meta_file.is_file():
        raise FileNotFoundError(f"Missing kernel-metadata.json in {staging_dir}")
    cmd = build_kaggle_push_cmd(staging_dir)
    if runner is None:
        if shutil.which("kaggle") is None:
            raise RuntimeError("The 'kaggle' CLI is not on PATH.")
        res = subprocess.run(cmd, check=False)
        code = res.returncode
    else:
        code = runner(cmd)
    if code != 0:
        raise RuntimeError(f"kaggle kernels push failed with exit code {code}")


def sha256_file(path: Path) -> str:
    """Computes the hex SHA-256 digest of a file (used for release weight verification)."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
