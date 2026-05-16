from __future__ import annotations

from bilimanga_dl.core.models import ChapterImages, SeriesInfo
from bilimanga_dl.sites.base import SiteAdapter
from bilimanga_dl.sites.bilimanga import BilimangaAdapter

DETAIL_HTML = """
<html><body>
<h1 class="book-title">新世紀福音戰士 完全版</h1>
<ol class="module-slide-ol volchapters">
  <li><a href="/detail/285/vol_24326.html"><h3>新世紀福音戰士 完全版 1</h3></a></li>
</ol>
</body></html>
"""

VOLUME_HTML = """
<html><body>
<h1 class="book-title">新世紀福音戰士 完全版 1</h1>
<ul class="module-content">
  <li class="chapter-li jsChapter">
    <a href="/read/285/24327.html" class="chapter-li-a">
      <span class="chapter-title">STAGE.１ 使徒、來襲</span>
    </a>
  </li>
  <li class="chapter-li jsChapter">
    <a href="/read/285/24328.html" class="chapter-li-a">
      <span class="chapter-title">STAGE.２ 再會</span>
    </a>
  </li>
</ul>
</body></html>
"""

READER_HTML = """
<html><body>
<script>
var ReadParams={
  mangaid:'285',
  manganame:'新世紀福音戰士 完全版',
  chapterid:'24327',
  chaptername:'第１卷 STAGE.１ 使徒、來襲'
}
</script>
<div id="acontentz">
  <img class="imagecontent" data-src="https://i.motiezw.com/0/285/24327/524971.avif">
  <img class="imagecontent" data-src="https://i.motiezw.com/0/285/24327/524972.avif">
</div>
</body></html>
"""


class FakeEngine:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.fetches: list[str] = []

    async def fetch_page(self, url: str) -> str:
        self.fetches.append(url)
        return self.pages[url]

    async def get_bytes(self, url: str, *, referer: str | None = None) -> bytes:
        return b"image"


class FailingEngine(FakeEngine):
    async def fetch_page(self, url: str) -> str:
        raise RuntimeError("offline")


def test_bilimanga_adapter_satisfies_site_adapter_contract() -> None:
    adapter = BilimangaAdapter()

    assert isinstance(adapter, SiteAdapter)
    assert adapter.name == "bilimanga.net"
    assert adapter.mirrors == ["https://www.bilimanga.net"]
    assert adapter.needs_browser is False


def test_url_matching_and_identifier_parsing() -> None:
    adapter = BilimangaAdapter()

    assert adapter.matches_url("https://www.bilimanga.net/detail/285.html") is True
    assert adapter.matches_url("https://www.bilimanga.net/read/285/24327.html") is True
    assert adapter.matches_url("https://example.com/detail/285.html") is False
    assert adapter.parse_identifier("https://www.bilimanga.net/detail/285.html") == "285"
    assert adapter.parse_identifier("https://www.bilimanga.net/detail/285/vol_24326.html") == "285"
    assert adapter.parse_identifier("https://www.bilimanga.net/read/285/24327.html") == "285"
    assert adapter.parse_identifier("285") == "285"
    assert adapter.parse_identifier("not-a-bilimanga-url") is None


async def test_get_series_hydrates_volumes_into_framework_model() -> None:
    adapter = BilimangaAdapter()
    engine = FakeEngine(
        {
            "https://www.bilimanga.net/detail/285.html": DETAIL_HTML,
            "https://www.bilimanga.net/detail/285/vol_24326.html": VOLUME_HTML,
        }
    )

    series = await adapter.get_series(engine, "285")

    assert isinstance(series, SeriesInfo)
    assert series.title == "新世紀福音戰士 完全版"
    assert series.url == "https://www.bilimanga.net/detail/285.html"
    assert series.hash_id == "285"
    assert [chapter.title for chapter in series.chapters] == [
        "STAGE.１ 使徒、來襲",
        "STAGE.２ 再會",
    ]
    assert [chapter.chapter_id for chapter in series.chapters] == [24327, 24328]
    assert engine.fetches == [
        "https://www.bilimanga.net/detail/285.html",
        "https://www.bilimanga.net/detail/285/vol_24326.html",
    ]


async def test_get_chapter_images_uses_reader_url_cached_from_series() -> None:
    adapter = BilimangaAdapter()
    engine = FakeEngine(
        {
            "https://www.bilimanga.net/detail/285.html": DETAIL_HTML,
            "https://www.bilimanga.net/detail/285/vol_24326.html": VOLUME_HTML,
            "https://www.bilimanga.net/read/285/24327.html": READER_HTML,
        }
    )
    await adapter.get_series(engine, "285")

    images = await adapter.get_chapter_images(engine, 24327)

    assert images == ChapterImages(
        title="第１卷 STAGE.１ 使徒、來襲",
        chapter_label="第１卷 STAGE.１ 使徒、來襲",
        image_urls=[
            "https://i.motiezw.com/0/285/24327/524971.avif",
            "https://i.motiezw.com/0/285/24327/524972.avif",
        ],
    )


async def test_get_chapter_images_returns_none_when_url_was_not_cached() -> None:
    adapter = BilimangaAdapter()
    engine = FakeEngine({})

    assert await adapter.get_chapter_images(engine, 99999) is None


async def test_search_is_safe_noop_until_reliable_bilimanga_search_exists() -> None:
    adapter = BilimangaAdapter()

    assert await adapter.search(FakeEngine({}), "eva") == []


def test_deduplicate_is_noop_for_bilimanga_chapters() -> None:
    adapter = BilimangaAdapter()
    chapters = []

    assert adapter.deduplicate(chapters) == (chapters, [])


async def test_probe_alive_returns_false_on_fetch_failure() -> None:
    adapter = BilimangaAdapter()

    assert await adapter.probe_alive(FailingEngine({})) is False
