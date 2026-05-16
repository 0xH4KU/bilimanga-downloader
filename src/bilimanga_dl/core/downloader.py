"""Image download helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse


@dataclass(frozen=True)
class DownloadResult:
    """Summary for one chapter image download."""

    chapter_dir: Path
    total: int
    downloaded: int
    skipped: int


class ByteClient(Protocol):
    """Minimal byte-fetching interface used by the downloader."""

    async def get_bytes(self, url: str, *, referer: str | None = None) -> bytes: ...


def sanitize_dirname(name: str) -> str:
    """Return a filesystem-safe directory segment."""
    name = re.sub(r'[\\/*?"<>|:]', " ", name)
    name = name.replace("..", "")
    name = re.sub(r"\s+", " ", name)
    return name.strip(" .") or "download"


class ImageDownloader:
    """Download ordered chapter images into numbered files."""

    def __init__(self, client: ByteClient, *, output_dir: str | Path = "downloads") -> None:
        self._client = client
        self._output_dir = Path(output_dir)

    async def download_images(
        self,
        series_title: str,
        chapter_title: str,
        image_urls: list[str],
        *,
        referer: str | None = None,
    ) -> DownloadResult:
        chapter_dir = self._output_dir / sanitize_dirname(series_title) / sanitize_dirname(chapter_title)
        chapter_dir.mkdir(parents=True, exist_ok=True)

        if (chapter_dir / ".complete").exists():
            return DownloadResult(chapter_dir=chapter_dir, total=len(image_urls), downloaded=0, skipped=len(image_urls))

        downloaded = 0
        skipped = 0
        for index, url in enumerate(image_urls, start=1):
            path = chapter_dir / f"{index:03d}{_guess_extension(url)}"
            if path.exists() and path.stat().st_size > 0:
                skipped += 1
                continue
            body = await self._client.get_bytes(url, referer=referer)
            path.write_bytes(body)
            downloaded += 1

        if downloaded + skipped == len(image_urls):
            (chapter_dir / ".complete").touch()
        return DownloadResult(chapter_dir=chapter_dir, total=len(image_urls), downloaded=downloaded, skipped=skipped)


def _guess_extension(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".avif", ".webp", ".jpg", ".jpeg", ".png", ".gif"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".jpg"
