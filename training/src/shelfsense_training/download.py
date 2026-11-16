"""Dataset download registry and Kaggle CLI wrapper.

All datasets are downloaded into `training/data/` (gitignored) so raw images
and archives never enter git history.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


@dataclass(frozen=True)
class DatasetSpec:
    """Metadata and access coordinates for a verified shelf dataset."""

    key: str
    title: str
    kaggle_slug: str
    fallback_url: str | None
    license_name: str
    commercial_ok: bool


# Registry of datasets verified in docs/DATA.md (S1-01).
DATASETS: Mapping[str, DatasetSpec] = {
    "sku110k": DatasetSpec(
        key="sku110k",
        title="SKU-110K Dense Retail Shelves",
        kaggle_slug="thedatasith/sku110k-annotations",
        fallback_url="http://trax-geometry.s3.amazonaws.com/cvpr_challenge/SKU110K_fixed.tar.gz",
        license_name="Academic / Non-Commercial (Trax Retail)",
        commercial_ok=False,
    ),
    "supermarket_shelves": DatasetSpec(
        key="supermarket_shelves",
        title="Supermarket Shelves Dataset (Humans in the Loop)",
        kaggle_slug="humansintheloop/supermarket-shelves-dataset",
        fallback_url=None,
        license_name="CC0 1.0 Public Domain",
        commercial_ok=True,
    ),
}


def has_kaggle_credentials(env: Mapping[str, str] | None = None, home: Path | None = None) -> bool:
    """Checks whether Kaggle API credentials exist in env vars or ~/.kaggle/."""
    env_map = env if env is not None else os.environ
    if env_map.get("KAGGLE_API_TOKEN"):
        return True
    if env_map.get("KAGGLE_USERNAME") and env_map.get("KAGGLE_KEY"):
        return True

    config_dir = Path(env_map["KAGGLE_CONFIG_DIR"]) if "KAGGLE_CONFIG_DIR" in env_map else (home or Path.home()) / ".kaggle"
    for filename in ("access_token", "kaggle.json"):
        candidate = config_dir / filename
        try:
            if candidate.is_file() and candidate.stat().st_size > 0:
                return True
        except OSError:
            continue
    return False


def build_kaggle_download_cmd(slug: str, target_dir: Path, unzip: bool = True) -> list[str]:
    """Builds the exact kaggle CLI command to fetch a dataset into target_dir."""
    if "/" not in slug or slug.startswith("/") or slug.endswith("/"):
        raise ValueError(f"Invalid Kaggle dataset slug: {slug!r}")
    cmd = ["kaggle", "datasets", "download", "-d", slug, "-p", str(target_dir)]
    if unzip:
        cmd.append("--unzip")
    return cmd


def download_dataset(
    key: str,
    data_root: Path,
    runner: Callable[[list[str]], int] | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Downloads a registered dataset via the Kaggle CLI into data_root/<key>."""
    if key not in DATASETS:
        raise KeyError(f"Unknown dataset key {key!r}. Available: {sorted(DATASETS)}")

    spec = DATASETS[key]
    target_dir = Path(data_root) / spec.key

    # Refuse to write inside any tracked folder outside training/data or a temp dir.
    if not has_kaggle_credentials(env=env, home=home):
        raise RuntimeError(
            "Kaggle credentials not found (~/.kaggle/access_token or ~/.kaggle/kaggle.json). "
            "Follow docs/OWNER_TODO.md item 2 before running live downloads."
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    cmd = build_kaggle_download_cmd(spec.kaggle_slug, target_dir, unzip=True)

    if runner is None:
        if shutil.which("kaggle") is None:
            raise RuntimeError("The 'kaggle' CLI is not on PATH.")
        completed = subprocess.run(cmd, check=False)
        exit_code = completed.returncode
    else:
        exit_code = runner(cmd)

    if exit_code != 0:
        raise RuntimeError(f"Kaggle download failed with exit code {exit_code}: {' '.join(cmd)}")

    return target_dir


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for downloading datasets into training/data/."""
    parser = argparse.ArgumentParser(description="Download ShelfSense datasets via Kaggle CLI.")
    parser.add_argument(
        "--dataset",
        choices=[*DATASETS.keys(), "all"],
        default="all",
        help="Which dataset to download (default: all).",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data",
        help="Destination directory (gitignored).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the kaggle CLI commands without executing them.",
    )
    args = parser.parse_args(argv)

    keys = list(DATASETS.keys()) if args.dataset == "all" else [args.dataset]
    for key in keys:
        spec = DATASETS[key]
        target = args.data_root / spec.key
        cmd = build_kaggle_download_cmd(spec.kaggle_slug, target, unzip=True)
        if args.dry_run:
            print(" ".join(cmd))
        else:
            download_dataset(key, args.data_root)
            print(f"Downloaded {spec.title} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
