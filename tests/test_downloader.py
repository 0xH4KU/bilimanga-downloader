from __future__ import annotations

import pytest

from bilimanga_dl.core.downloader import DownloadResult, ImageDownloader, sanitize_dirname


class FakeHttpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    async def get_bytes(self, url: str, *, referer: str | None = None) -> bytes:
        self.calls.append((url, referer))
        if url.endswith(".avif"):
            return b"\x00\x00\x00 ftypavif"
        return b"\xff\xd8\xff\xe0"


class FailingHttpClient:
    async def get_bytes(self, url: str, *, referer: str | None = None) -> bytes:
        raise RuntimeError(f"HTTP 403 for {url}")


def test_sanitize_dirname_removes_path_unsafe_characters() -> None:
    assert sanitize_dirname('STAGE.１ / 使徒:*?"<>|') == "STAGE.１ 使徒"
    assert sanitize_dirname("...") == "download"


async def test_download_images_writes_numbered_files_and_uses_referer(tmp_path) -> None:
    client = FakeHttpClient()
    downloader = ImageDownloader(client, output_dir=tmp_path)

    result = await downloader.download_images(
        "新世紀福音戰士 完全版",
        "STAGE.１ 使徒、來襲",
        [
            "https://i.motiezw.com/0/285/24327/524971.avif",
            "https://i.motiezw.com/0/285/24327/524972.jpg",
        ],
        referer="https://www.bilimanga.net/read/285/24327.html",
    )

    chapter_dir = tmp_path / "新世紀福音戰士 完全版" / "STAGE.１ 使徒、來襲"
    assert result == DownloadResult(chapter_dir=chapter_dir, total=2, downloaded=2, skipped=0)
    assert (chapter_dir / "001.avif").read_bytes() == b"\x00\x00\x00 ftypavif"
    assert (chapter_dir / "002.jpg").read_bytes() == b"\xff\xd8\xff\xe0"
    assert (chapter_dir / ".complete").exists()
    assert client.calls == [
        ("https://i.motiezw.com/0/285/24327/524971.avif", "https://www.bilimanga.net/read/285/24327.html"),
        ("https://i.motiezw.com/0/285/24327/524972.jpg", "https://www.bilimanga.net/read/285/24327.html"),
    ]


async def test_download_images_skips_completed_chapter(tmp_path) -> None:
    client = FakeHttpClient()
    chapter_dir = tmp_path / "Title" / "Chapter"
    chapter_dir.mkdir(parents=True)
    (chapter_dir / ".complete").touch()

    result = await ImageDownloader(client, output_dir=tmp_path).download_images(
        "Title",
        "Chapter",
        ["https://i.motiezw.com/0/1/2/3.avif"],
    )

    assert result == DownloadResult(chapter_dir=chapter_dir, total=1, downloaded=0, skipped=1)
    assert client.calls == []


async def test_download_images_does_not_mark_complete_when_image_fails(tmp_path) -> None:
    downloader = ImageDownloader(FailingHttpClient(), output_dir=tmp_path)

    with pytest.raises(RuntimeError, match="HTTP 403"):
        await downloader.download_images(
            "Title",
            "Chapter",
            ["https://i.motiezw.com/0/285/24327/524971.avif"],
        )

    assert not (tmp_path / "Title" / "Chapter" / ".complete").exists()
