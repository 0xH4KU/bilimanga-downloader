from __future__ import annotations

from pathlib import Path

import pytest

from bilimanga_dl.core.client import BilimangaClient
from bilimanga_dl.core.downloader import DownloadResult
from bilimanga_dl.core.errors import BrowserTimeoutError, HttpStatusError

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
      <span class="chapter-title">STAGE.２ 再會⋯⋯</span>
    </a>
  </li>
</ul>
</body></html>
"""


READER_HTML_1 = """
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


READER_HTML_2 = """
<html><body>
<script>
var ReadParams={
  mangaid:'285',
  manganame:'新世紀福音戰士 完全版',
  chapterid:'24328',
  chaptername:'第１卷 STAGE.２ 再會⋯⋯'
}
</script>
<div id="acontentz">
  <img class="imagecontent" data-src="https://i.motiezw.com/0/285/24328/525001.avif">
</div>
</body></html>
"""


class FakeHttpClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.text_urls: list[str] = []
        self.byte_urls: list[str] = []

    async def get_text(self, url: str, *, referer: str | None = None) -> str:
        self.text_urls.append(url)
        return self.pages[url]

    async def get_bytes(self, url: str, *, referer: str | None = None) -> bytes:
        self.byte_urls.append(url)
        raise RuntimeError("HTTP 403")


class FakeReaderRenderer:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.urls: list[str] = []

    async def render(self, url: str) -> str:
        self.urls.append(url)
        return self.pages[url]

    async def fetch_image(self, url: str, *, referer: str | None = None) -> bytes:
        return b"browser-image"


class TimeoutReaderRenderer(FakeReaderRenderer):
    async def render(self, url: str) -> str:
        raise TimeoutError("reader took too long")


class StatusFailingHttpClient(FakeHttpClient):
    async def get_bytes(self, url: str, *, referer: str | None = None) -> bytes:
        self.byte_urls.append(url)
        raise HttpStatusError(status_code=500, url=url)


class ForbiddenPageHttpClient(FakeHttpClient):
    async def get_text(self, url: str, *, referer: str | None = None) -> str:
        self.text_urls.append(url)
        raise HttpStatusError(status_code=403, url=url)


class FakeDownloader:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.calls: list[tuple[str, str, list[str], str | None]] = []

    async def download_images(
        self,
        series_title: str,
        chapter_title: str,
        image_urls: list[str],
        *,
        referer: str | None = None,
    ) -> DownloadResult:
        self.calls.append((series_title, chapter_title, image_urls, referer))
        return DownloadResult(
            chapter_dir=self.output_dir / series_title / chapter_title,
            total=len(image_urls),
            downloaded=len(image_urls),
            skipped=0,
        )


class MixedResultDownloader(FakeDownloader):
    async def download_images(
        self,
        series_title: str,
        chapter_title: str,
        image_urls: list[str],
        *,
        referer: str | None = None,
    ) -> DownloadResult:
        self.calls.append((series_title, chapter_title, image_urls, referer))
        failed = 1 if "STAGE.２" in chapter_title else 0
        chapter_dir = self.output_dir / series_title / chapter_title
        chapter_dir.mkdir(parents=True, exist_ok=True)
        for index in range(1, max(0, len(image_urls) - failed) + 1):
            (chapter_dir / f"{index:03d}.jpg").write_bytes(b"\xff\xd8")
        return DownloadResult(
            chapter_dir=chapter_dir,
            total=len(image_urls),
            downloaded=max(0, len(image_urls) - failed),
            skipped=0,
            failed=failed,
            failed_files=("002",) if failed else (),
        )


async def test_download_url_expands_series_and_respects_limits(tmp_path: Path) -> None:
    http = FakeHttpClient(
        {
            "https://www.bilimanga.net/detail/285.html": DETAIL_HTML,
            "https://www.bilimanga.net/detail/285/vol_24326.html": VOLUME_HTML,
            "https://www.bilimanga.net/read/285/24327.html": READER_HTML_1,
            "https://www.bilimanga.net/read/285/24328.html": READER_HTML_2,
        }
    )
    reader = FakeReaderRenderer(
        {
            "https://www.bilimanga.net/read/285/24327.html": READER_HTML_1,
            "https://www.bilimanga.net/read/285/24328.html": READER_HTML_2,
        }
    )
    downloader = FakeDownloader(tmp_path)
    client = BilimangaClient(http_client=http, reader=reader, downloader=downloader)

    summary = await client.download_url(
        "https://www.bilimanga.net/detail/285.html",
        chapter_limit=1,
        image_limit=1,
    )

    assert http.text_urls == [
        "https://www.bilimanga.net/detail/285.html",
        "https://www.bilimanga.net/detail/285/vol_24326.html",
        "https://www.bilimanga.net/read/285/24327.html",
    ]
    assert reader.urls == []
    assert downloader.calls == [
        (
            "新世紀福音戰士 完全版",
            "第１卷 STAGE.１ 使徒、來襲",
            ["https://i.motiezw.com/0/285/24327/524971.avif"],
            "https://www.bilimanga.net/read/285/24327.html",
        )
    ]
    assert summary.series_title == "新世紀福音戰士 完全版"
    assert summary.total_chapters == 1
    assert summary.total_images == 1
    assert summary.downloaded == 1


async def test_download_url_accepts_direct_chapter_url(tmp_path: Path) -> None:
    downloader = FakeDownloader(tmp_path)
    client = BilimangaClient(
        http_client=FakeHttpClient({"https://www.bilimanga.net/read/285/24327.html": READER_HTML_1}),
        reader=FakeReaderRenderer({}),
        downloader=downloader,
    )

    summary = await client.download_url("https://www.bilimanga.net/read/285/24327.html", image_limit=2)

    assert downloader.calls[0][:3] == (
        "新世紀福音戰士 完全版",
        "第１卷 STAGE.１ 使徒、來襲",
        [
            "https://i.motiezw.com/0/285/24327/524971.avif",
            "https://i.motiezw.com/0/285/24327/524972.avif",
        ],
    )
    assert summary.total_chapters == 1
    assert summary.total_images == 2


async def test_download_url_summary_tracks_failed_partial_bytes_and_issues(tmp_path: Path) -> None:
    reader_html_2_partial = READER_HTML_2.replace(
        "</div>",
        '  <img class="imagecontent" data-src="https://i.motiezw.com/0/285/24328/525002.avif">\n</div>',
    )
    downloader = MixedResultDownloader(tmp_path)
    client = BilimangaClient(
        http_client=FakeHttpClient(
            {
                "https://www.bilimanga.net/detail/285.html": DETAIL_HTML,
                "https://www.bilimanga.net/detail/285/vol_24326.html": VOLUME_HTML,
                "https://www.bilimanga.net/read/285/24327.html": READER_HTML_1,
                "https://www.bilimanga.net/read/285/24328.html": reader_html_2_partial,
            }
        ),
        reader=FakeReaderRenderer({}),
        downloader=downloader,
        output_dir=tmp_path,
    )

    summary = await client.download_url("https://www.bilimanga.net/detail/285.html")

    assert summary.downloaded == 3
    assert summary.failed == 1
    assert summary.partial == 1
    assert summary.total_bytes > 0
    assert summary.issues[0].chapter_title == "第１卷 STAGE.２ 再會⋯⋯"
    assert summary.issues[0].kind == "partial"


async def test_download_url_records_missing_images_issue(tmp_path: Path) -> None:
    no_images_html = READER_HTML_1.replace(
        '<img class="imagecontent" data-src="https://i.motiezw.com/0/285/24327/524971.avif">',
        "",
    ).replace(
        '<img class="imagecontent" data-src="https://i.motiezw.com/0/285/24327/524972.avif">',
        "",
    )
    client = BilimangaClient(
        http_client=FakeHttpClient({"https://www.bilimanga.net/read/285/24327.html": no_images_html}),
        reader=FakeReaderRenderer({"https://www.bilimanga.net/read/285/24327.html": no_images_html}),
        downloader=FakeDownloader(tmp_path),
        output_dir=tmp_path,
    )

    summary = await client.download_url("https://www.bilimanga.net/read/285/24327.html")

    assert summary.total_chapters == 1
    assert summary.failed == 1
    assert summary.issues[0].chapter_title == "第１卷 STAGE.１ 使徒、來襲"
    assert summary.issues[0].kind == "missing_images"
    assert summary.issues[0].message == "no images found on reader page"


async def test_download_url_applies_chapter_selection_and_filters(tmp_path: Path) -> None:
    downloader = FakeDownloader(tmp_path)
    client = BilimangaClient(
        http_client=FakeHttpClient(
            {
                "https://www.bilimanga.net/detail/285.html": DETAIL_HTML,
                "https://www.bilimanga.net/detail/285/vol_24326.html": VOLUME_HTML,
                "https://www.bilimanga.net/read/285/24327.html": READER_HTML_1,
                "https://www.bilimanga.net/read/285/24328.html": READER_HTML_2,
            }
        ),
        reader=FakeReaderRenderer({}),
        downloader=downloader,
        output_dir=tmp_path,
    )

    summary = await client.download_url(
        "https://www.bilimanga.net/detail/285.html",
        chapters_selection="1",
        chapter_filters=["+再會"],
    )

    assert summary.total_chapters == 1
    assert downloader.calls[0][1] == "第１卷 STAGE.２ 再會⋯⋯"


async def test_load_chapter_falls_back_to_reader_when_http_has_no_images() -> None:
    blocked_html = """
    <html><body>
    <script>
    var ReadParams={
      mangaid:'285',
      manganame:'新世紀福音戰士 完全版',
      chapterid:'24327',
      chaptername:'第１卷 STAGE.１ 使徒、來襲'
    }
    </script>
    <div id="acontentz"><center>抱歉，章節不支持桌面電腦端瀏覽器顯示</center></div>
    </body></html>
    """
    reader = FakeReaderRenderer({"https://www.bilimanga.net/read/285/24327.html": READER_HTML_1})
    client = BilimangaClient(
        http_client=FakeHttpClient({"https://www.bilimanga.net/read/285/24327.html": blocked_html}),
        reader=reader,
        downloader=FakeDownloader(Path("downloads")),
    )

    chapter = await client.load_chapter("https://www.bilimanga.net/read/285/24327.html")

    assert reader.urls == ["https://www.bilimanga.net/read/285/24327.html"]
    assert len(chapter.image_urls) == 2


async def test_client_image_bytes_fall_back_to_reader_after_http_failure() -> None:
    http = FakeHttpClient({})
    reader = FakeReaderRenderer({})
    client = BilimangaClient(http_client=http, reader=reader)

    body = await client.get_image_bytes(
        "https://i.motiezw.com/0/285/24327/524971.avif",
        referer="https://www.bilimanga.net/read/285/24327.html",
    )

    assert body == b"browser-image"
    assert http.byte_urls == ["https://i.motiezw.com/0/285/24327/524971.avif"]


async def test_client_fetch_page_uses_http_when_reader_html_contains_images() -> None:
    http = FakeHttpClient({"https://www.bilimanga.net/read/285/24327.html": READER_HTML_1})
    reader = FakeReaderRenderer({})
    client = BilimangaClient(http_client=http, reader=reader)

    html = await client.fetch_page("https://www.bilimanga.net/read/285/24327.html")

    assert html == READER_HTML_1
    assert reader.urls == []


async def test_client_fetch_page_falls_back_to_reader_when_reader_html_has_no_images() -> None:
    blocked_html = """
    <html><body>
    <script>
    var ReadParams={
      mangaid:'285',
      manganame:'新世紀福音戰士 完全版',
      chapterid:'24327',
      chaptername:'第１卷 STAGE.１ 使徒、來襲'
    }
    </script>
    <div id="acontentz"><center>抱歉，章節不支持桌面電腦端瀏覽器顯示</center></div>
    </body></html>
    """
    http = FakeHttpClient({"https://www.bilimanga.net/read/285/24327.html": blocked_html})
    reader = FakeReaderRenderer({"https://www.bilimanga.net/read/285/24327.html": READER_HTML_1})
    client = BilimangaClient(http_client=http, reader=reader)

    html = await client.fetch_page("https://www.bilimanga.net/read/285/24327.html")

    assert html == READER_HTML_1
    assert reader.urls == ["https://www.bilimanga.net/read/285/24327.html"]


async def test_client_fetch_page_falls_back_to_reader_after_forbidden_http_status() -> None:
    http = ForbiddenPageHttpClient({})
    reader = FakeReaderRenderer({"https://www.bilimanga.net/read/285/24327.html": READER_HTML_1})
    client = BilimangaClient(http_client=http, reader=reader)

    html = await client.fetch_page("https://www.bilimanga.net/read/285/24327.html")

    assert html == READER_HTML_1
    assert reader.urls == ["https://www.bilimanga.net/read/285/24327.html"]


async def test_client_get_bytes_falls_back_only_for_forbidden_http_status() -> None:
    http = StatusFailingHttpClient({})
    reader = FakeReaderRenderer({})
    client = BilimangaClient(http_client=http, reader=reader)

    with pytest.raises(HttpStatusError) as exc_info:
        await client.get_bytes("https://i.motiezw.com/0/285/24327/524971.avif")

    assert exc_info.value.status_code == 500


async def test_client_fetch_page_wraps_reader_timeout() -> None:
    blocked_html = """
    <html><body>
    <script>
    var ReadParams={
      mangaid:'285',
      manganame:'新世紀福音戰士 完全版',
      chapterid:'24327',
      chaptername:'第１卷 STAGE.１ 使徒、來襲'
    }
    </script>
    <div id="acontentz"><center>抱歉，章節不支持桌面電腦端瀏覽器顯示</center></div>
    </body></html>
    """
    http = FakeHttpClient({"https://www.bilimanga.net/read/285/24327.html": blocked_html})
    client = BilimangaClient(http_client=http, reader=TimeoutReaderRenderer({}))

    with pytest.raises(BrowserTimeoutError, match="reader fallback"):
        await client.fetch_page("https://www.bilimanga.net/read/285/24327.html")
