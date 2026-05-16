"""Image download helpers."""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from bilimanga_dl.core.errors import PartialDownloadError
from bilimanga_dl.core.fileio import atomic_write_bytes, atomic_write_text

_COMPLETE_MARKER = ".complete"
_STATE_FILE = "chapter.state.json"


@dataclass(frozen=True)
class DownloadConfig:
    """Downloader behavior knobs."""

    max_concurrent_images: int = 4
    max_retries: int = 3
    retry_delay: float = 1.0
    image_delay: float = 0.0


@dataclass(frozen=True)
class DownloadProgress:
    """Snapshot emitted after a page is processed."""

    completed: int
    total: int
    failed: int
    skipped: int
    current_file: str
    total_bytes: int = 0


ProgressCallback = Callable[[DownloadProgress], None]


@dataclass(frozen=True)
class _PageDownloadResult:
    filename: str
    url: str
    status: str
    error: str | None = None


@dataclass(frozen=True)
class DownloadResult:
    """Summary for one chapter image download."""

    chapter_dir: Path
    total: int
    downloaded: int
    skipped: int
    failed: int = 0
    failed_files: tuple[str, ...] = ()

    @property
    def status(self) -> str:
        if self.failed == self.total and self.total > 0:
            return "failed"
        if self.failed > 0:
            return "partial"
        if self.downloaded == 0 and self.skipped == self.total:
            return "skipped"
        return "complete"

    def ensure_complete(self, chapter_title: str) -> None:
        """Raise a domain error when this result is partial."""
        if self.status != "partial":
            return
        raise PartialDownloadError(f"{chapter_title} is incomplete: {self.failed}/{self.total} image(s) failed.")


class ByteClient(Protocol):
    """Minimal byte-fetching interface used by the downloader."""

    async def get_bytes(self, url: str, *, referer: str | None = None) -> bytes: ...


def sanitize_dirname(name: str) -> str:
    """Return a filesystem-safe directory segment."""
    name = re.sub(r'[\\/*?"<>|:]', " ", name)
    name = name.replace("..", "")
    name = re.sub(r"\s+", " ", name)
    return name.strip(" .") or "download"


def _validate_within_base(path: Path, base: Path) -> None:
    if not path.resolve().is_relative_to(base.resolve()):
        raise ValueError(f"Path traversal detected: {path} escapes base directory {base}")


class ImageDownloader:
    """Download ordered chapter images into numbered files."""

    def __init__(
        self,
        client: ByteClient,
        *,
        output_dir: str | Path = "downloads",
        config: DownloadConfig | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        self._client = client
        self._output_dir = Path(output_dir)
        self._config = config or DownloadConfig()
        self._on_progress = on_progress
        self.bytes_downloaded = 0
        self.retry_count = 0

    def chapter_dir(self, series_title: str, chapter_title: str) -> Path:
        """Return the safe output directory for one chapter."""
        path = self._output_dir / sanitize_dirname(series_title) / sanitize_dirname(chapter_title)
        _validate_within_base(path, self._output_dir)
        return path

    async def download_images(
        self,
        series_title: str,
        chapter_title: str,
        image_urls: list[str],
        *,
        referer: str | None = None,
    ) -> DownloadResult:
        chapter_dir = self.chapter_dir(series_title, chapter_title)
        chapter_dir.mkdir(parents=True, exist_ok=True)

        if (chapter_dir / _COMPLETE_MARKER).exists():
            result = DownloadResult(
                chapter_dir=chapter_dir,
                total=len(image_urls),
                downloaded=0,
                skipped=len(image_urls),
            )
            self._emit_progress(
                len(image_urls),
                len(image_urls),
                failed=0,
                skipped=len(image_urls),
                current_file="(skipped)",
            )
            return result

        existing_files = self._index_existing_downloads(chapter_dir)
        total = len(image_urls)
        progress_done = 0
        progress_failed = 0
        progress_skipped = 0
        progress_lock = asyncio.Lock()
        semaphore = asyncio.Semaphore(max(1, self._config.max_concurrent_images))

        async def advance(filename: str, *, failed: int = 0, skipped: int = 0) -> None:
            nonlocal progress_done, progress_failed, progress_skipped
            async with progress_lock:
                progress_done += 1
                progress_failed += failed
                progress_skipped += skipped
                self._emit_progress(
                    progress_done,
                    total,
                    failed=progress_failed,
                    skipped=progress_skipped,
                    current_file=filename,
                )

        async def fetch_one(index: int, url: str) -> _PageDownloadResult:
            async with semaphore:
                if self._config.image_delay > 0:
                    await asyncio.sleep(self._config.image_delay)

                filename = f"{index:03d}"
                existing = existing_files.pop(filename, [])
                if existing and any(self._is_valid_image_file(path) for path in existing):
                    await advance(filename, skipped=1)
                    return _PageDownloadResult(filename=filename, url=url, status="skip")
                for stale in existing:
                    with contextlib.suppress(OSError):
                        stale.unlink()

                success, error = await self._download_image(url, chapter_dir, filename, referer=referer)
                await advance(filename, failed=0 if success else 1)
                return _PageDownloadResult(
                    filename=filename,
                    url=url,
                    status="ok" if success else "fail",
                    error=error,
                )

        page_results = await asyncio.gather(
            *[fetch_one(index, url) for index, url in enumerate(image_urls, start=1)]
        )
        downloaded = sum(1 for result in page_results if result.status == "ok")
        skipped = sum(1 for result in page_results if result.status == "skip")
        failed_results = [result for result in page_results if result.status == "fail"]
        failed = len(failed_results)
        result = DownloadResult(
            chapter_dir=chapter_dir,
            total=total,
            downloaded=downloaded,
            skipped=skipped,
            failed=failed,
            failed_files=tuple(item.filename for item in failed_results),
        )

        if failed == 0:
            (chapter_dir / _COMPLETE_MARKER).touch()
            self._remove_state_file(chapter_dir)
        else:
            self._write_state_file(chapter_dir, series_title, chapter_title, result, failed_results)
        return result

    def _emit_progress(self, completed: int, total: int, *, failed: int, skipped: int, current_file: str) -> None:
        if self._on_progress is None:
            return
        self._on_progress(
            DownloadProgress(
                completed=completed,
                total=total,
                failed=failed,
                skipped=skipped,
                current_file=current_file,
                total_bytes=self.bytes_downloaded,
            )
        )

    async def _download_image(
        self,
        url: str,
        output_dir: Path,
        filename: str,
        *,
        referer: str | None = None,
    ) -> tuple[bool, str | None]:
        last_error: str | None = None
        for attempt in range(self._config.max_retries + 1):
            try:
                body = await self._client.get_bytes(url, referer=referer)
                path = output_dir / f"{filename}{_guess_extension(url, body)}"
                atomic_write_bytes(path, body, sync=False)
                self.bytes_downloaded += len(body)
                return True, None
            except Exception as exc:
                last_error = str(exc)
                if attempt < self._config.max_retries:
                    self.retry_count += 1
                    if self._config.retry_delay > 0:
                        await asyncio.sleep(self._config.retry_delay * (2**attempt))
        return False, last_error

    @staticmethod
    def _index_existing_downloads(chapter_dir: Path) -> dict[str, list[Path]]:
        indexed: dict[str, list[Path]] = {}
        for entry in chapter_dir.iterdir():
            if not entry.is_file():
                continue
            if entry.name in {_COMPLETE_MARKER, _STATE_FILE}:
                continue
            if entry.name.endswith(".part") or (entry.name.startswith(".") and entry.name.endswith(".tmp")):
                with contextlib.suppress(OSError):
                    entry.unlink()
                continue
            indexed.setdefault(entry.stem, []).append(entry)
        return indexed

    @staticmethod
    def _is_valid_image_file(path: Path) -> bool:
        try:
            header = path.read_bytes()[:16]
        except OSError:
            return False
        if not header:
            return False
        suffix = path.suffix.lower()
        if suffix == ".webp":
            return header[:4] == b"RIFF" and header[8:12] == b"WEBP"
        if suffix == ".png":
            return header[:8] == b"\x89PNG\r\n\x1a\n"
        if suffix in {".jpg", ".jpeg"}:
            return header[:2] == b"\xff\xd8"
        if suffix == ".gif":
            return header[:4] == b"GIF8"
        if suffix == ".bmp":
            return header[:2] == b"BM"
        if suffix == ".avif":
            return len(header) >= 12 and header[4:12] == b"ftypavif"
        return False

    @staticmethod
    def _remove_state_file(chapter_dir: Path) -> None:
        with contextlib.suppress(OSError):
            (chapter_dir / _STATE_FILE).unlink()

    @staticmethod
    def _write_state_file(
        chapter_dir: Path,
        series_title: str,
        chapter_title: str,
        result: DownloadResult,
        failed_results: list[_PageDownloadResult],
    ) -> None:
        payload = {
            "updated_at": datetime.now(UTC).isoformat(),
            "series_title": series_title,
            "chapter": chapter_title,
            "status": result.status,
            "total": result.total,
            "downloaded": result.downloaded,
            "skipped": result.skipped,
            "failed": result.failed,
            "failed_pages": [
                {"filename": item.filename, "url": item.url, "error": item.error or "unknown error"}
                for item in failed_results
            ],
        }
        atomic_write_text(chapter_dir / _STATE_FILE, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _guess_extension(url: str, data: bytes = b"") -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".avif", ".webp", ".jpg", ".jpeg", ".png", ".gif", ".bmp"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    if data[:4] == b"GIF8":
        return ".gif"
    if len(data) >= 12 and data[4:12] == b"ftypavif":
        return ".avif"
    if data[:2] == b"BM":
        return ".bmp"
    return ".jpg"
