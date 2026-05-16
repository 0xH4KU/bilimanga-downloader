from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from bilimanga_dl import sites
from bilimanga_dl.core.errors import ConfigurationError
from bilimanga_dl.sites.base import SiteAdapter

if TYPE_CHECKING:
    from collections.abc import Generator

    from bilimanga_dl.core.models import ChapterImages, ChapterInfo, DedupDecision, SearchResult, SeriesInfo
    from bilimanga_dl.sites.base import Engine


@dataclass
class _StubAdapter:
    name: str
    mirrors: list[str] = field(default_factory=list)
    needs_browser: bool = False
    matched_urls: tuple[str, ...] = ()

    def matches_url(self, url: str) -> bool:
        return url in self.matched_urls

    def parse_identifier(self, url_or_slug: str) -> str | None:
        value = url_or_slug.strip()
        return value or None

    async def on_engine_ready(self, engine: Engine) -> None:
        return None

    async def probe_alive(self, engine: Engine) -> bool:
        return True

    async def search(self, engine: Engine, query: str, *, limit: int = 20) -> list[SearchResult]:
        return []

    async def get_series(self, engine: Engine, identifier: str) -> SeriesInfo:
        raise NotImplementedError

    async def get_chapter_images(self, engine: Engine, chapter_id: int) -> ChapterImages | None:
        raise NotImplementedError

    def deduplicate(self, chapters: list[ChapterInfo]) -> tuple[list[ChapterInfo], list[DedupDecision]]:
        return chapters, []


@pytest.fixture(autouse=True)
def _isolate_registry() -> Generator[None, None, None]:
    sites.clear()
    yield
    sites.clear()


def test_stub_adapter_satisfies_protocol() -> None:
    assert isinstance(_StubAdapter(name="stub"), SiteAdapter)


def test_register_get_unregister_adapter() -> None:
    adapter = _StubAdapter(name="stub")
    sites.register(adapter)

    assert sites.get_by_name("stub") is adapter
    assert sites.get_active() is adapter

    sites.unregister("stub")
    with pytest.raises(ConfigurationError, match="Unknown site adapter"):
        sites.get_by_name("stub")


def test_get_for_url_returns_first_matching_adapter() -> None:
    a = _StubAdapter(name="a", matched_urls=("https://a.example/item",))
    b = _StubAdapter(name="b", matched_urls=("https://b.example/item",))
    sites.register(a)
    sites.register(b)

    assert sites.get_for_url("https://b.example/item") is b
    assert sites.get_for_url("https://missing.example/item") is None


def test_get_active_rejects_empty_or_ambiguous_registry() -> None:
    with pytest.raises(ConfigurationError, match="No site adapter"):
        sites.get_active()

    sites.register(_StubAdapter(name="a"))
    sites.register(_StubAdapter(name="b"))

    with pytest.raises(ConfigurationError, match="Multiple site adapters"):
        sites.get_active()
