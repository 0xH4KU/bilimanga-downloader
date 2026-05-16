from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from bilimanga_dl.core import cli
from bilimanga_dl.core.client import DownloadSummary


class FakeClient:
    instances: ClassVar[list[FakeClient]] = []

    def __init__(self, *, output_dir: str | Path, headless: bool = True) -> None:
        self.output_dir = Path(output_dir)
        self.headless = headless
        self.calls: list[tuple[str, int | None, int | None]] = []
        FakeClient.instances.append(self)

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def download_url(
        self,
        url: str,
        *,
        chapter_limit: int | None = None,
        image_limit: int | None = None,
    ) -> DownloadSummary:
        self.calls.append((url, chapter_limit, image_limit))
        return DownloadSummary(
            series_title="新世紀福音戰士 完全版",
            total_chapters=1,
            total_images=2,
            downloaded=2,
            skipped=0,
            output_dir=self.output_dir,
        )


def test_download_command_passes_limits_to_client(monkeypatch, tmp_path: Path, capsys) -> None:
    FakeClient.instances = []
    monkeypatch.setattr(cli, "BilimangaClient", FakeClient)

    result = cli.main(
        [
            "download",
            "https://www.bilimanga.net/read/285/24327.html",
            "--output",
            str(tmp_path),
            "--limit",
            "1",
            "--image-limit",
            "2",
            "--headed",
        ]
    )

    assert result == 0
    assert FakeClient.instances[0].headless is False
    assert FakeClient.instances[0].calls == [("https://www.bilimanga.net/read/285/24327.html", 1, 2)]
    assert "新世紀福音戰士 完全版" in capsys.readouterr().out
