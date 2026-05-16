"""Framework / site adapter contract."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeAlias, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from bilimanga_dl.core.models import ChapterImages, ChapterInfo, DedupDecision, SearchResult, SeriesInfo


OnEngineReadyHook: TypeAlias = "Callable[[Engine], Awaitable[None]]"


@runtime_checkable
class Engine(Protocol):
    """Transport boundary used by site adapters."""

    async def fetch_page(self, url: str) -> str:
        """Fetch or render *url* and return HTML."""
        ...

    async def get_bytes(self, url: str, *, referer: str | None = None) -> bytes:
        """Fetch binary content."""
        ...


@runtime_checkable
class SiteAdapter(Protocol):
    """Per-site behaviour required by the framework."""

    name: str
    mirrors: list[str]
    needs_browser: bool

    def matches_url(self, url: str) -> bool:
        """Return whether *url* belongs to this site."""
        ...

    def parse_identifier(self, url_or_slug: str) -> str | None:
        """Extract a canonical series identifier from a URL or bare id."""
        ...

    async def on_engine_ready(self, engine: Engine) -> None:
        """Run one-time engine setup for this adapter."""
        ...

    async def probe_alive(self, engine: Engine) -> bool:
        """Return whether the active mirror is reachable."""
        ...

    async def search(self, engine: Engine, query: str, *, limit: int = 20) -> list[SearchResult]:
        """Run keyword search."""
        ...

    async def get_series(self, engine: Engine, identifier: str) -> SeriesInfo:
        """Fetch full series metadata and chapters."""
        ...

    async def get_chapter_images(self, engine: Engine, chapter_id: int) -> ChapterImages | None:
        """Fetch ordered chapter images."""
        ...

    def deduplicate(self, chapters: list[ChapterInfo]) -> tuple[list[ChapterInfo], list[DedupDecision]]:
        """Collapse duplicate chapters by site-specific rules."""
        ...


__all__ = ["Engine", "OnEngineReadyHook", "SiteAdapter"]
