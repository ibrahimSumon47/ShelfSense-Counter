"""Unit tests for the Kaggle dataset downloader and credential checks."""
from pathlib import Path
import pytest

from shelfsense_training.download import (
    DATASETS,
    build_kaggle_download_cmd,
    download_dataset,
    has_kaggle_credentials,
)


def test_registered_datasets_match_data_card() -> None:
    """Both SKU-110K and Supermarket Shelves are registered with licence flags."""
    assert "sku110k" in DATASETS
    assert "supermarket_shelves" in DATASETS
    assert DATASETS["sku110k"].commercial_ok is False
    assert DATASETS["supermarket_shelves"].commercial_ok is True


def test_build_kaggle_download_cmd() -> None:
    """Command uses the standard kaggle datasets download flags."""
    target = Path("/tmp/data/sku110k")
    cmd = build_kaggle_download_cmd("thedatasith/sku110k-annotations", target, unzip=True)
    assert cmd == ["kaggle", "datasets", "download", "-d", "thedatasith/sku110k-annotations", "-p", str(target), "--unzip"]


def test_build_kaggle_download_cmd_rejects_bad_slug() -> None:
    """Malformed slugs without owner/dataset are rejected upfront."""
    with pytest.raises(ValueError, match="Invalid Kaggle dataset slug"):
        build_kaggle_download_cmd("invalidslug", Path("/tmp/out"))


def test_has_kaggle_credentials_detects_env_and_files(tmp_path: Path) -> None:
    """Credential helper checks env vars first, then ~/.kaggle/access_token and kaggle.json."""
    assert has_kaggle_credentials(env={}, home=tmp_path) is False
    assert has_kaggle_credentials(env={"KAGGLE_API_TOKEN": "tok_123"}, home=tmp_path) is True
    assert has_kaggle_credentials(env={"KAGGLE_USERNAME": "u", "KAGGLE_KEY": "k"}, home=tmp_path) is True

    kaggle_dir = tmp_path / ".kaggle"
    kaggle_dir.mkdir()
    token_file = kaggle_dir / "access_token"
    token_file.write_text("secret", encoding="utf-8")
    assert has_kaggle_credentials(env={}, home=tmp_path) is True


def test_download_dataset_invokes_runner_when_authenticated(tmp_path: Path) -> None:
    """When credentials exist, download_dataset creates the folder and runs kaggle CLI."""
    recorded: list[list[str]] = []

    def fake_runner(cmd: list[str]) -> int:
        recorded.append(cmd)
        return 0

    out = download_dataset(
        "supermarket_shelves",
        data_root=tmp_path,
        runner=fake_runner,
        env={"KAGGLE_API_TOKEN": "dummy_token"},
    )
    assert out == tmp_path / "supermarket_shelves"
    assert out.is_dir()
    assert len(recorded) == 1
    assert "humansintheloop/supermarket-shelves-dataset" in recorded[0]


def test_download_dataset_raises_clearly_when_unauthenticated(tmp_path: Path) -> None:
    """Missing credentials produce an actionable error pointing to docs/OWNER_TODO.md."""
    with pytest.raises(RuntimeError, match="docs/OWNER_TODO.md"):
        download_dataset("sku110k", data_root=tmp_path, env={}, home=tmp_path)
