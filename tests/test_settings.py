from __future__ import annotations

import json
from pathlib import Path

from bilimanga_dl.core.downloader import DownloadConfig
from bilimanga_dl.core.settings import (
    DownloadTuning,
    Settings,
    SettingsRepository,
    load_settings,
    save_settings,
)


def test_settings_defaults_target_bilimanga_config_dir() -> None:
    settings = Settings()

    assert settings.output_dir == str(Path.home() / "Downloads" / "bilimanga-dl")
    assert settings.default_format == "pdf"
    assert settings.concurrency_profile == "desktop"
    assert settings.concurrent_chapters == 2
    assert settings.concurrent_images == 8
    assert settings.max_retries == 3


def test_settings_repository_round_trip(tmp_path: Path) -> None:
    repository = SettingsRepository(tmp_path / "settings.json")
    original = Settings(
        output_dir="/tmp/bilimanga",
        default_format="both",
        concurrency_profile="custom",
        concurrent_chapters=3,
        concurrent_images=4,
        max_retries=5,
        download_delay=False,
        optimize_images=False,
    )

    repository.save(original)
    loaded = repository.load()

    assert loaded == original
    data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert data["version"] == 1


def test_settings_repository_normalizes_invalid_values(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "version": 1,
                "default_format": "zip",
                "concurrency_profile": "broken",
                "concurrent_chapters": 0,
                "concurrent_images": 0,
                "max_retries": 99,
                "download_delay": "yes",
                "optimize_images": "no",
            }
        ),
        encoding="utf-8",
    )

    settings = SettingsRepository(settings_file).load()

    assert settings.default_format == "pdf"
    assert settings.concurrency_profile == "custom"
    assert settings.concurrent_chapters == 1
    assert settings.concurrent_images == 1
    assert settings.max_retries == 10
    assert settings.download_delay is True
    assert settings.optimize_images is True


def test_settings_repository_returns_defaults_for_corrupt_json(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{broken", encoding="utf-8")

    settings = SettingsRepository(settings_file).load()

    assert settings == Settings()


def test_resolve_download_tuning_uses_profiles() -> None:
    assert SettingsRepository.resolve_download_tuning(Settings(concurrency_profile="desktop")) == DownloadTuning(
        concurrent_chapters=2,
        concurrent_images=8,
        download_delay=True,
    )
    assert SettingsRepository.resolve_download_tuning(Settings(concurrency_profile="low_resource")) == DownloadTuning(
        concurrent_chapters=1,
        concurrent_images=2,
        download_delay=True,
    )
    assert SettingsRepository.resolve_download_tuning(Settings(concurrency_profile="ci")) == DownloadTuning(
        concurrent_chapters=1,
        concurrent_images=4,
        download_delay=False,
    )


def test_build_download_config_from_settings() -> None:
    settings = Settings(concurrency_profile="custom", concurrent_images=3, max_retries=4, download_delay=False)

    config = SettingsRepository.build_download_config(settings)

    assert config == DownloadConfig(max_concurrent_images=3, max_retries=4, retry_delay=1.0, image_delay=0.0)


def test_default_settings_wrappers_use_default_repository(monkeypatch, tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("bilimanga_dl.core.settings._SETTINGS_FILE", settings_file)

    save_settings(Settings(default_format="cbz"))
    settings = load_settings()

    assert settings.default_format == "cbz"
