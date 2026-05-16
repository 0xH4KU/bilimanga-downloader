"""Persistent user settings for bilimanga-dl."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, ClassVar

from bilimanga_dl.core.downloader import DownloadConfig
from bilimanga_dl.core.fileio import atomic_write_text

logger = logging.getLogger(__name__)

_SETTINGS_FILE = Path.home() / ".config" / "bilimanga-dl" / "settings.json"
_CURRENT_SETTINGS_VERSION = 1


@dataclass(frozen=True)
class DownloadTuning:
    """Effective download tuning resolved from a concurrency profile."""

    concurrent_images: int
    download_delay: bool


@dataclass(frozen=True)
class Settings:
    """User-configurable settings persisted as JSON."""

    output_dir: str = str(Path.home() / "Downloads" / "bilimanga-dl")
    default_format: str = "pdf"
    concurrency_profile: str = "desktop"
    concurrent_images: int = 8
    max_retries: int = 3
    download_delay: bool = True
    optimize_images: bool = True


class SettingsRepository:
    """Repository for loading and saving normalized user settings."""

    _ALLOWED_FORMATS: ClassVar[set[str]] = {"pdf", "cbz", "both"}
    _PROFILE_PRESETS: ClassVar[dict[str, DownloadTuning]] = {
        "desktop": DownloadTuning(concurrent_images=8, download_delay=True),
        "low_resource": DownloadTuning(concurrent_images=2, download_delay=True),
        "ci": DownloadTuning(concurrent_images=4, download_delay=False),
    }
    _CUSTOM_PROFILE: ClassVar[str] = "custom"
    _ALLOWED_PROFILES: ClassVar[set[str]] = set(_PROFILE_PRESETS) | {_CUSTOM_PROFILE}

    def __init__(self, settings_file: Path | None = None) -> None:
        self._settings_file = settings_file or _SETTINGS_FILE

    def load(self) -> Settings:
        """Load settings from disk, falling back to defaults on invalid files."""
        if not self._settings_file.exists():
            return Settings()
        try:
            data = json.loads(self._settings_file.read_text(encoding="utf-8"))
            return self._deserialize(data)
        except Exception as exc:
            logger.warning("Failed to load settings: %s", exc)
            return Settings()

    def save(self, settings: Settings) -> None:
        """Persist normalized settings."""
        normalized = self._normalize_settings(asdict(settings))
        payload = {"version": _CURRENT_SETTINGS_VERSION, **asdict(normalized)}
        atomic_write_text(
            self._settings_file,
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        )

    @classmethod
    def build_download_config(cls, settings: Settings) -> DownloadConfig:
        """Build downloader runtime knobs from persisted settings."""
        tuning = cls.resolve_download_tuning(settings)
        return DownloadConfig(
            max_concurrent_images=tuning.concurrent_images,
            max_retries=settings.max_retries,
            retry_delay=1.0,
            image_delay=0.15 if tuning.download_delay else 0.0,
        )

    @classmethod
    def resolve_download_tuning(cls, settings: Settings) -> DownloadTuning:
        """Resolve effective concurrency from the selected profile."""
        if settings.concurrency_profile == cls._CUSTOM_PROFILE:
            return DownloadTuning(
                concurrent_images=settings.concurrent_images,
                download_delay=settings.download_delay,
            )
        return cls._PROFILE_PRESETS.get(settings.concurrency_profile, cls._PROFILE_PRESETS["desktop"])

    def _deserialize(self, data: object) -> Settings:
        if not isinstance(data, dict):
            logger.warning("Settings file did not contain an object; using defaults.")
            return Settings()
        version = data.get("version")
        if version is not None and not isinstance(version, int):
            logger.warning("Settings version %r is invalid; using defaults.", version)
            return Settings()
        if isinstance(version, int) and version > _CURRENT_SETTINGS_VERSION:
            logger.warning(
                "Settings version %d is newer than supported version %d; using defaults.",
                version,
                _CURRENT_SETTINGS_VERSION,
            )
            return Settings()
        return self._normalize_settings(data)

    def _normalize_settings(self, data: dict[str, Any]) -> Settings:
        defaults = Settings()
        concurrent_images = self._normalize_int(
            data.get("concurrent_images"),
            default=defaults.concurrent_images,
            minimum=1,
            maximum=16,
            field_name="concurrent_images",
        )
        download_delay = self._normalize_bool(
            data.get("download_delay"),
            default=defaults.download_delay,
            field_name="download_delay",
        )
        return Settings(
            output_dir=self._normalize_output_dir(data.get("output_dir"), defaults.output_dir),
            default_format=self._normalize_format(data.get("default_format"), defaults.default_format),
            concurrency_profile=self._normalize_profile(
                data.get("concurrency_profile"),
                concurrent_images=concurrent_images,
                download_delay=download_delay,
            ),
            concurrent_images=concurrent_images,
            max_retries=self._normalize_int(
                data.get("max_retries"),
                default=defaults.max_retries,
                minimum=0,
                maximum=10,
                field_name="max_retries",
            ),
            download_delay=download_delay,
            optimize_images=self._normalize_bool(
                data.get("optimize_images"),
                default=defaults.optimize_images,
                field_name="optimize_images",
            ),
        )

    @staticmethod
    def _normalize_output_dir(value: object, default: str) -> str:
        if isinstance(value, str) and value.strip():
            return value
        return default

    def _normalize_format(self, value: object, default: str) -> str:
        if isinstance(value, str) and value in self._ALLOWED_FORMATS:
            return value
        if value is not None:
            logger.warning("Settings field default_format=%r is invalid; using %r.", value, default)
        return default

    @classmethod
    def _normalize_profile(cls, value: object, *, concurrent_images: int, download_delay: bool) -> str:
        if isinstance(value, str) and value in cls._ALLOWED_PROFILES:
            return value
        if value is not None:
            logger.warning("Settings field concurrency_profile=%r is invalid; inferring a safe profile.", value)

        desktop = cls._PROFILE_PRESETS["desktop"]
        if concurrent_images == desktop.concurrent_images and download_delay is desktop.download_delay:
            return "desktop"
        return cls._CUSTOM_PROFILE

    @staticmethod
    def _normalize_bool(value: object, *, default: bool, field_name: str) -> bool:
        if isinstance(value, bool):
            return value
        if value is not None:
            logger.warning("Settings field %s=%r is invalid; using %r.", field_name, value, default)
        return default

    @staticmethod
    def _normalize_int(
        value: object,
        *,
        default: int,
        minimum: int,
        maximum: int,
        field_name: str,
    ) -> int:
        if value is None:
            normalized = default
        elif isinstance(value, (int, float, str)):
            try:
                normalized = int(value)
            except (TypeError, ValueError):
                logger.warning("Settings field %s=%r is invalid; using %d.", field_name, value, default)
                return default
        else:
            logger.warning("Settings field %s=%r is invalid; using %d.", field_name, value, default)
            return default
        if normalized < minimum or normalized > maximum:
            clamped = max(minimum, min(maximum, normalized))
            logger.warning("Settings field %s=%r is out of range; clamping to %d.", field_name, value, clamped)
            return clamped
        return normalized


def load_settings() -> Settings:
    """Load settings from the default repository."""
    return SettingsRepository().load()


def save_settings(settings: Settings) -> None:
    """Save settings through the default repository."""
    SettingsRepository().save(settings)
