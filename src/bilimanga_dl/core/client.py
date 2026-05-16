"""Application orchestration for bilimanga parsing and downloads."""

from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, Self

from bilimanga_dl.core.converters import collect_images
from bilimanga_dl.core.downloader import DownloadResult, ImageDownloader
from bilimanga_dl.core.errors import BrowserTimeoutError, HttpStatusError
from bilimanga_dl.core.fileio import atomic_write_text
from bilimanga_dl.core.http import BilimangaHttpClient
from bilimanga_dl.core.models import Chapter, Series, Volume
from bilimanga_dl.core.reader import PlaywrightBrowser
from bilimanga_dl.core.reporting import DownloadIssue
from bilimanga_dl.core.selection import apply_chapter_filters, parse_chapter_selection
from bilimanga_dl.core.verify import ExpectedChapter, VerifyReport, VerifyStatus, build_verify_report
from bilimanga_dl.sites.bilimanga import BilimangaParser

if TYPE_CHECKING:
    from types import TracebackType


@dataclass(frozen=True)
class DownloadedChapter:
    """One chapter output produced or skipped by a download run."""

    title: str
    volume_title: str
    chapter_dir: Path


@dataclass(frozen=True)
class DownloadSummary:
    """Aggregate result for a download command."""

    series_title: str
    total_chapters: int
    total_images: int
    downloaded: int
    skipped: int
    output_dir: Path
    partial: int = 0
    failed: int = 0
    total_bytes: int = 0
    issues: tuple[DownloadIssue, ...] = ()
    chapters: tuple[DownloadedChapter, ...] = ()


@dataclass(frozen=True)
class _ChapterOutcome:
    result: DownloadResult | None = None
    downloaded_chapter: DownloadedChapter | None = None
    issue: DownloadIssue | None = None
    series_title: str = ""


class TextBytesClient(Protocol):
    """Page and image transport used by the client."""

    async def get_text(self, url: str, *, referer: str | None = None) -> str: ...

    async def get_bytes(self, url: str, *, referer: str | None = None) -> bytes: ...

    async def aclose(self) -> None: ...


class ReaderRenderer(Protocol):
    """Rendered reader-page fallback."""

    async def render(self, url: str) -> str: ...

    async def fetch_image(self, url: str, *, referer: str | None = None) -> bytes: ...


class ChapterDownloader(Protocol):
    """Image download interface used by download_url."""

    async def download_images(
        self,
        series_title: str,
        chapter_title: str,
        image_urls: list[str],
        *,
        referer: str | None = None,
    ) -> DownloadResult: ...


class BilimangaClient:
    """Coordinate site parsing, reader rendering, and image downloads."""

    def __init__(
        self,
        *,
        http_client: TextBytesClient | None = None,
        reader: ReaderRenderer | None = None,
        downloader: ChapterDownloader | None = None,
        parser: BilimangaParser | None = None,
        output_dir: str | Path = "downloads",
        headless: bool = True,
    ) -> None:
        self._own_http = http_client is None
        self._own_reader = reader is None
        self._http = http_client or BilimangaHttpClient()
        self._browser = PlaywrightBrowser(headless=headless) if reader is None else None
        self._reader = reader
        self._reader_lock = asyncio.Lock()
        self._parser = parser or BilimangaParser()
        self.output_dir = Path(output_dir)
        self._downloader = downloader or ImageDownloader(self, output_dir=self.output_dir)

    async def __aenter__(self) -> Self:
        if self._reader is None:
            assert self._browser is not None
            self._reader = await self._browser.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._own_reader and self._browser is not None:
            await self._browser.aclose()
        if self._own_http:
            await self._http.aclose()

    async def load_series(self, url: str) -> Series:
        """Fetch a detail page and hydrate all linked volumes."""
        html = await self._http.get_text(url)
        series = self._parser.parse_series_detail(html, url)
        hydrated: list[Volume] = []
        for volume in series.volumes:
            hydrated.append(await self.load_volume(volume.url))
        series.volumes = hydrated
        return series

    async def load_volume(self, url: str) -> Volume:
        """Fetch a volume page and parse chapter links."""
        html = await self._http.get_text(url)
        return self._parser.parse_volume(html, url)

    async def load_chapter(self, url: str) -> Chapter:
        """Fetch and parse a reader page, rendering only when HTTP is blocked."""
        html = await self.fetch_page(url)
        return self._parser.parse_reader(html, url)

    async def fetch_page(self, url: str) -> str:
        """Engine-facing page fetch API with reader-page render fallback."""
        parsed = self._parser.parse_url(url)
        try:
            html = await self._http.get_text(url)
        except HttpStatusError as exc:
            if parsed.kind == "chapter" and exc.status_code in {403, 429}:
                return await self._render_reader_page(url, context="reader fallback")
            raise
        if parsed.kind != "chapter":
            return html

        chapter = self._parser.parse_reader(html, url)
        if chapter.image_urls:
            return html
        return await self._render_reader_page(url, context="reader fallback")

    async def get_bytes(self, url: str, *, referer: str | None = None) -> bytes:
        """Downloader-facing byte fetch API."""
        return await self.get_image_bytes(url, referer=referer)

    async def get_image_bytes(self, url: str, *, referer: str | None = None) -> bytes:
        """Fetch image bytes via HTTP, falling back to browser image loading."""
        try:
            return await self._http.get_bytes(url, referer=referer)
        except HttpStatusError as exc:
            if exc.status_code not in {403, 429}:
                raise
            return await self._fetch_image_with_reader(url, referer=referer)
        except RuntimeError as exc:
            if "HTTP 403" not in str(exc) and "403 Forbidden" not in str(exc):
                raise
            return await self._fetch_image_with_reader(url, referer=referer)

    async def _render_reader_page(self, url: str, *, context: str) -> str:
        reader = await self._ensure_reader()
        try:
            return await reader.render(url)
        except TimeoutError as exc:
            raise BrowserTimeoutError(f"Timed out during {context}: {url}") from exc

    async def _fetch_image_with_reader(self, url: str, *, referer: str | None = None) -> bytes:
        reader = await self._ensure_reader()
        try:
            return await reader.fetch_image(url, referer=referer)
        except TimeoutError as exc:
            raise BrowserTimeoutError(f"Timed out fetching image with browser: {url}") from exc

    async def download_url(
        self,
        url: str,
        *,
        chapter_limit: int | None = None,
        image_limit: int | None = None,
        chapters_selection: str = "all",
        chapter_filters: list[str] | None = None,
        chapter_concurrency: int = 1,
    ) -> DownloadSummary:
        """Download a series, volume, or chapter URL."""
        series_title, chapters = await self._resolve_chapters(
            url,
            chapter_limit=chapter_limit,
            chapters_selection=chapters_selection,
            chapter_filters=chapter_filters,
        )
        return await self._download_chapters(
            series_title,
            chapters,
            image_limit=image_limit,
            chapter_concurrency=chapter_concurrency,
        )

    async def _download_chapters(
        self,
        series_title: str,
        chapters: list[Chapter],
        *,
        image_limit: int | None,
        chapter_concurrency: int,
    ) -> DownloadSummary:
        resolved_series_title = series_title or next(
            (chapter_stub.series_title for chapter_stub in chapters if chapter_stub.series_title),
            "",
        )
        semaphore = asyncio.Semaphore(max(1, chapter_concurrency))

        async def download_one(chapter_stub: Chapter) -> _ChapterOutcome:
            async with semaphore:
                return await self._download_chapter_stub(
                    chapter_stub,
                    series_title=resolved_series_title,
                    image_limit=image_limit,
                )

        raw_outcomes = await asyncio.gather(*[download_one(chapter_stub) for chapter_stub in chapters])

        results: list[DownloadResult] = []
        issues: list[DownloadIssue] = []
        downloaded_chapters: list[DownloadedChapter] = []
        for outcome in raw_outcomes:
            if outcome.result is not None:
                results.append(outcome.result)
            if outcome.downloaded_chapter is not None:
                downloaded_chapters.append(outcome.downloaded_chapter)
            if outcome.issue is not None:
                issues.append(outcome.issue)
        if not resolved_series_title:
            resolved_series_title = next((outcome.series_title for outcome in raw_outcomes if outcome.series_title), "")

        return DownloadSummary(
            series_title=resolved_series_title or "bilimanga",
            total_chapters=len(chapters),
            total_images=sum(result.total for result in results),
            downloaded=sum(result.downloaded for result in results),
            skipped=sum(result.skipped for result in results),
            output_dir=self.output_dir,
            partial=sum(1 for result in results if result.status == "partial"),
            failed=sum(result.failed for result in results) + len(issues),
            total_bytes=sum(_chapter_bytes(result.chapter_dir) for result in results),
            issues=(*_issues_from_results(results), *issues),
            chapters=tuple(downloaded_chapters),
        )

    async def verify_url(
        self,
        url: str,
        *,
        chapter_limit: int | None = None,
        chapters_selection: str = "all",
        chapter_filters: list[str] | None = None,
        refresh_image_counts: bool = False,
    ) -> VerifyReport:
        """Compare local downloads with the remote chapter list."""
        series_title, chapters = await self._resolve_chapters(
            url,
            chapter_limit=chapter_limit,
            chapters_selection=chapters_selection,
            chapter_filters=chapter_filters,
        )
        expected: list[ExpectedChapter] = []
        resolved_series_title = series_title
        for chapter_stub in chapters:
            resolved_chapter = chapter_stub
            image_count: int | None = None
            if refresh_image_counts or not chapter_stub.title or not resolved_series_title:
                resolved_chapter = await self.load_chapter(chapter_stub.url)
                if not resolved_series_title:
                    resolved_series_title = (
                        resolved_chapter.series_title
                        or chapter_stub.series_title
                        or self._infer_series_title(resolved_chapter)
                    )
                if refresh_image_counts:
                    image_count = len(resolved_chapter.image_urls)
            expected.append(ExpectedChapter(chapter=resolved_chapter, expected_image_count=image_count))
        return build_verify_report(resolved_series_title, expected, self.output_dir)

    async def repair_report(
        self,
        report: VerifyReport,
        *,
        chapter_concurrency: int = 1,
    ) -> DownloadSummary:
        """Redownload chapters that failed verification."""
        for item in report.items:
            if item.status == VerifyStatus.COMPLETE or item.local_dir is None:
                continue
            with contextlib.suppress(OSError):
                (item.local_dir / ".complete").unlink()
            if item.status == VerifyStatus.IMAGE_MISMATCH:
                for image_path in collect_images(item.local_dir):
                    with contextlib.suppress(OSError):
                        image_path.unlink()
        return await self._download_chapters(
            report.series_title,
            list(report.repair_chapters),
            image_limit=None,
            chapter_concurrency=chapter_concurrency,
        )

    async def _download_chapter_stub(
        self,
        chapter_stub: Chapter,
        *,
        series_title: str,
        image_limit: int | None,
    ) -> _ChapterOutcome:
        try:
            chapter = await self.load_chapter(chapter_stub.url)
            resolved_series_title = series_title or chapter.series_title or self._infer_series_title(chapter)
            image_urls = chapter.image_urls[:image_limit] if image_limit is not None else chapter.image_urls
            if not image_urls:
                return _ChapterOutcome(
                    issue=DownloadIssue(
                        chapter_title=chapter.title,
                        kind="missing_images",
                        message="no images found on reader page",
                    ),
                    series_title=resolved_series_title,
                )
            result = await self._downloader.download_images(
                resolved_series_title,
                chapter.title,
                image_urls,
                referer=chapter.url,
            )
            downloaded_chapter = DownloadedChapter(
                title=chapter.title,
                volume_title=chapter_stub.volume_title
                or chapter.volume_title
                or _volume_title_from_chapter(chapter.title),
                chapter_dir=result.chapter_dir,
            )
            _write_chapter_metadata(
                result.chapter_dir,
                series_title=resolved_series_title,
                volume_title=downloaded_chapter.volume_title,
                chapter=chapter,
                expected_image_count=len(image_urls),
            )
            return _ChapterOutcome(
                result=result,
                downloaded_chapter=downloaded_chapter,
                series_title=resolved_series_title,
            )
        except Exception as exc:
            return _ChapterOutcome(
                issue=DownloadIssue(
                    chapter_title=chapter_stub.title or chapter_stub.url,
                    kind="chapter_failed",
                    message=str(exc) or exc.__class__.__name__,
                ),
            )

    async def _resolve_chapters(
        self,
        url: str,
        *,
        chapter_limit: int | None = None,
        chapters_selection: str = "all",
        chapter_filters: list[str] | None = None,
    ) -> tuple[str, list[Chapter]]:
        parsed = self._parser.parse_url(url)
        if parsed.kind == "series":
            series_title, chapters = await self._chapters_from_series(url)
        elif parsed.kind == "volume":
            volume = await self.load_volume(url)
            series_title = volume.title
            chapters = list(volume.chapters)
        elif parsed.kind == "chapter":
            series_title, chapters = "", [Chapter(parsed.manga_id or 0, parsed.chapter_id or 0, "", url)]
        else:
            raise ValueError(f"Unsupported bilimanga URL: {url}")

        if chapter_limit is not None:
            chapters = chapters[:chapter_limit]
        if chapter_filters:
            chapters = apply_chapter_filters(chapters, chapter_filters)
        chapters = parse_chapter_selection(chapters_selection, chapters)
        return series_title, chapters

    async def _chapters_from_series(self, url: str) -> tuple[str, list[Chapter]]:
        series = await self.load_series(url)
        chapters: list[Chapter] = []
        for volume in series.volumes:
            chapters.extend(volume.chapters)
        return series.title, chapters

    async def _ensure_reader(self) -> ReaderRenderer:
        if self._reader is None:
            async with self._reader_lock:
                if self._reader is None:
                    assert self._browser is not None
                    self._reader = await self._browser.start()
        return self._reader

    @staticmethod
    def _infer_series_title(chapter: Chapter) -> str:
        if " " in chapter.title:
            return chapter.title.split(" ", 1)[0]
        return "bilimanga"


def _chapter_bytes(chapter_dir: Path) -> int:
    if not chapter_dir.exists():
        return 0
    return sum(path.stat().st_size for path in chapter_dir.iterdir() if path.is_file())


def _volume_title_from_chapter(chapter_title: str) -> str:
    if " " in chapter_title:
        return chapter_title.split(" ", 1)[0]
    return "Volume"


def _write_chapter_metadata(
    chapter_dir: Path,
    *,
    series_title: str,
    volume_title: str,
    chapter: Chapter,
    expected_image_count: int,
) -> None:
    payload = {
        "series_title": series_title,
        "volume_title": volume_title,
        "title": chapter.title,
        "manga_id": chapter.manga_id,
        "chapter_id": chapter.chapter_id,
        "url": chapter.url,
        "expected_image_count": expected_image_count,
        "image_urls": chapter.image_urls,
    }
    atomic_write_text(chapter_dir / "chapter.meta.json", json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _issues_from_results(results: list[DownloadResult]) -> tuple[DownloadIssue, ...]:
    issues: list[DownloadIssue] = []
    for result in results:
        if result.status == "complete" or result.status == "skipped":
            continue
        chapter_title = result.chapter_dir.name
        if result.status == "failed":
            issues.append(
                DownloadIssue(
                    chapter_title=chapter_title,
                    kind="failed",
                    message="all image downloads failed",
                )
            )
            continue
        issues.append(
            DownloadIssue(
                chapter_title=chapter_title,
                kind="partial",
                message=f"{result.failed}/{result.total} image(s) failed",
            )
        )
    return tuple(issues)
