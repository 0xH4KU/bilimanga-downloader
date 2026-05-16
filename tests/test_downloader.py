from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from bilimanga_dl.core.downloader import (
    DownloadConfig,
    DownloadProgress,
    DownloadResult,
    ImageDownloader,
    sanitize_dirname,
)
from bilimanga_dl.core.errors import PartialDownloadError

if TYPE_CHECKING:
    from pathlib import Path


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


class FlakyHttpClient:
    def __init__(self, failures_before_success: int, body: bytes = b"\xff\xd8\xff\xe0") -> None:
        self.failures_before_success = failures_before_success
        self.body = body
        self.calls = 0

    async def get_bytes(self, url: str, *, referer: str | None = None) -> bytes:
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise RuntimeError("temporary failure")
        return self.body


class SelectiveHttpClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_bytes(self, url: str, *, referer: str | None = None) -> bytes:
        self.calls.append(url)
        if url.endswith("fail.jpg"):
            raise RuntimeError("blocked")
        return b"\xff\xd8\xff\xe0"


class FailsSecondOnceHttpClient:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.failed_second = False

    async def get_bytes(self, url: str, *, referer: str | None = None) -> bytes:
        self.calls.append(url)
        if url.endswith("2.jpg") and not self.failed_second:
            self.failed_second = True
            raise RuntimeError("temporary second-page failure")
        return b"\xff\xd8\xff\xe0"


def test_sanitize_dirname_removes_path_unsafe_characters() -> None:
    assert sanitize_dirname('STAGE.１ / 使徒:*?"<>|') == "STAGE.１ 使徒"
    assert sanitize_dirname("...") == "download"


def test_download_result_status_values(tmp_path: Path) -> None:
    assert DownloadResult(tmp_path, total=2, downloaded=0, skipped=2, failed=0).status == "skipped"
    assert DownloadResult(tmp_path, total=2, downloaded=2, skipped=0, failed=0).status == "complete"
    assert DownloadResult(tmp_path, total=2, downloaded=1, skipped=0, failed=1).status == "partial"
    assert DownloadResult(tmp_path, total=2, downloaded=0, skipped=0, failed=2).status == "failed"


def test_ensure_complete_download_raises_for_partial(tmp_path: Path) -> None:
    result = DownloadResult(tmp_path, total=3, downloaded=2, skipped=0, failed=1)

    with pytest.raises(PartialDownloadError, match=r"1/3 image"):
        result.ensure_complete("Chapter 1")


async def test_download_images_writes_numbered_files_and_uses_referer(tmp_path) -> None:
    client = FakeHttpClient()
    progress: list[DownloadProgress] = []
    downloader = ImageDownloader(
        client,
        output_dir=tmp_path,
        config=DownloadConfig(image_delay=0, max_retries=0),
        on_progress=progress.append,
    )

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
    assert result == DownloadResult(chapter_dir=chapter_dir, total=2, downloaded=2, skipped=0, failed=0)
    assert result.status == "complete"
    assert (chapter_dir / "001.avif").read_bytes() == b"\x00\x00\x00 ftypavif"
    assert (chapter_dir / "002.jpg").read_bytes() == b"\xff\xd8\xff\xe0"
    assert (chapter_dir / ".complete").exists()
    assert not (chapter_dir / "chapter.state.json").exists()
    assert progress[-1].completed == 2
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

    assert result == DownloadResult(chapter_dir=chapter_dir, total=1, downloaded=0, skipped=1, failed=0)
    assert result.status == "skipped"
    assert client.calls == []


async def test_download_images_records_failed_state_without_raising(tmp_path) -> None:
    downloader = ImageDownloader(
        FailingHttpClient(),
        output_dir=tmp_path,
        config=DownloadConfig(max_retries=0, image_delay=0),
    )

    result = await downloader.download_images(
        "Title",
        "Chapter",
        ["https://i.motiezw.com/0/285/24327/524971.avif"],
    )

    assert result.status == "failed"
    assert result.failed == 1
    assert result.failed_files == ("001",)
    assert not (tmp_path / "Title" / "Chapter" / ".complete").exists()
    state = json.loads((tmp_path / "Title" / "Chapter" / "chapter.state.json").read_text(encoding="utf-8"))
    assert state["status"] == "failed"
    assert state["failed_pages"][0]["filename"] == "001"


async def test_download_images_retries_before_success(tmp_path) -> None:
    client = FlakyHttpClient(failures_before_success=2)
    downloader = ImageDownloader(
        client,
        output_dir=tmp_path,
        config=DownloadConfig(max_retries=2, retry_delay=0, image_delay=0),
    )

    result = await downloader.download_images("Title", "Chapter", ["https://cdn.example/001.jpg"])

    assert result.status == "complete"
    assert client.calls == 3
    assert downloader.retry_count == 2


async def test_download_images_records_partial_and_recovers_on_rerun(tmp_path) -> None:
    client = FailsSecondOnceHttpClient()
    downloader = ImageDownloader(
        client,
        output_dir=tmp_path,
        config=DownloadConfig(max_retries=0, image_delay=0, max_concurrent_images=1),
    )

    first = await downloader.download_images(
        "Title",
        "Chapter",
        ["https://cdn.example/1.jpg", "https://cdn.example/2.jpg"],
    )

    assert first.status == "partial"
    assert first.downloaded == 1
    assert first.failed == 1
    assert not (first.chapter_dir / ".complete").exists()
    assert (first.chapter_dir / "chapter.state.json").exists()

    client.calls.clear()
    second = await downloader.download_images("Title", "Chapter", ["https://cdn.example/1.jpg", "https://cdn.example/2.jpg"])

    assert second.status == "complete"
    assert client.calls == ["https://cdn.example/2.jpg"]
    assert (second.chapter_dir / ".complete").exists()
    assert not (second.chapter_dir / "chapter.state.json").exists()


async def test_download_images_redownloads_corrupt_existing_file(tmp_path) -> None:
    client = FakeHttpClient()
    chapter_dir = tmp_path / "Title" / "Chapter"
    chapter_dir.mkdir(parents=True)
    (chapter_dir / "001.jpg").write_bytes(b"not-a-jpeg")

    result = await ImageDownloader(
        client,
        output_dir=tmp_path,
        config=DownloadConfig(max_retries=0, image_delay=0),
    ).download_images("Title", "Chapter", ["https://cdn.example/001.jpg"])

    assert result.status == "complete"
    assert client.calls == [("https://cdn.example/001.jpg", None)]
    assert (chapter_dir / "001.jpg").read_bytes().startswith(b"\xff\xd8")


def test_downloader_rejects_paths_that_escape_output_dir(tmp_path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    output = tmp_path / "out"
    output.mkdir()
    (output / "Title").symlink_to(outside, target_is_directory=True)
    downloader = ImageDownloader(FakeHttpClient(), output_dir=output)

    with pytest.raises(ValueError, match="Path traversal"):
        downloader.chapter_dir("Title", "Chapter")
