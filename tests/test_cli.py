from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

from bilimanga_dl.core import cli
from bilimanga_dl.core.client import DownloadedChapter, DownloadSummary
from bilimanga_dl.core.errors import ConversionError
from bilimanga_dl.core.history import HistoryEntry
from bilimanga_dl.core.models import ChapterInfo
from bilimanga_dl.core.settings import Settings


class FakeClient:
    instances: ClassVar[list[FakeClient]] = []

    def __init__(self, *, output_dir: str | Path, headless: bool = True) -> None:
        self.output_dir = Path(output_dir)
        self.headless = headless
        self.calls: list[tuple[str, int | None, int | None, int]] = []
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
        chapters_selection: str = "all",
        chapter_filters: list[str] | None = None,
        chapter_concurrency: int = 1,
    ) -> DownloadSummary:
        del chapters_selection, chapter_filters
        self.calls.append((url, chapter_limit, image_limit, chapter_concurrency))
        return DownloadSummary(
            series_title="新世紀福音戰士 完全版",
            total_chapters=1,
            total_images=2,
            downloaded=2,
            skipped=0,
            output_dir=self.output_dir,
        )


def _chapters() -> list[ChapterInfo]:
    return [
        ChapterInfo(title="STAGE.１ 使徒、來襲", chapter_id=1, number="1"),
        ChapterInfo(title="STAGE.２ 再會", chapter_id=2, number="2"),
        ChapterInfo(title="EXTRA 設定資料", chapter_id=3, number="3"),
    ]


def test_parser_supports_expected_commands_and_download_options() -> None:
    parser = cli.build_parser()

    download = parser.parse_args(
        [
            "download",
            "https://www.bilimanga.net/detail/285.html",
            "--chapters",
            "1-2",
            "--format",
            "both",
            "--package",
            "volume",
            "--filter",
            "+STAGE",
            "--chapter-concurrency",
            "3",
            "--output",
            "/tmp/out",
            "--no-optimize",
            "--quiet",
            "--debug",
        ]
    )
    assert download.command == "download"
    assert download.chapters == "1-2"
    assert download.filters == ["+STAGE"]
    assert download.format == "both"
    assert download.package == "volume"
    assert download.chapter_concurrency == 3
    assert download.output == "/tmp/out"
    assert download.no_optimize is True
    assert download.quiet is True
    assert download.debug is True

    assert parser.parse_args(["info", "285"]).command == "info"
    assert parser.parse_args(["list"]).command == "list"
    assert parser.parse_args(["clean", "--force"]).force is True
    assert parser.parse_args(["history", "clear"]).action == "clear"
    assert parser.parse_args(["doctor"]).command == "doctor"
    assert parser.parse_args(["settings"]).command == "settings"


def test_bare_url_is_download_shortcut(monkeypatch, tmp_path: Path) -> None:
    FakeClient.instances = []
    monkeypatch.setattr(cli, "BilimangaClient", FakeClient)
    monkeypatch.setattr(cli.SettingsRepository, "load", lambda self: Settings(output_dir=str(tmp_path)))

    result = cli.main(["https://www.bilimanga.net/read/285/24327.html"])

    assert result == 0
    assert FakeClient.instances[0].calls == [("https://www.bilimanga.net/read/285/24327.html", None, None, 2)]


def test_download_command_passes_legacy_limits_to_client(monkeypatch, tmp_path: Path, capsys) -> None:
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
            "--chapter-concurrency",
            "4",
            "--headed",
        ]
    )

    assert result == 0
    assert FakeClient.instances[0].headless is False
    assert FakeClient.instances[0].calls == [("https://www.bilimanga.net/read/285/24327.html", 1, 2, 4)]
    assert "新世紀福音戰士 完全版" in capsys.readouterr().out


def test_download_command_reports_conversion_failure(monkeypatch, tmp_path: Path, capsys) -> None:
    class CompleteClient(FakeClient):
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
            del url, chapter_limit, image_limit, chapters_selection, chapter_filters, chapter_concurrency
            chapter_dir = self.output_dir / "Series" / "Chapter"
            chapter_dir.mkdir(parents=True)
            (chapter_dir / ".complete").write_text("", encoding="utf-8")
            return DownloadSummary(
                series_title="Series",
                total_chapters=1,
                total_images=1,
                downloaded=1,
                skipped=0,
                output_dir=self.output_dir,
            )

    def fail_convert(chapter_dir: Path, fmt: str, *, optimize: bool) -> Path:
        del chapter_dir, fmt, optimize
        raise ConversionError("bad image")

    monkeypatch.setattr(cli, "BilimangaClient", CompleteClient)
    monkeypatch.setattr(cli, "convert", fail_convert)

    result = cli.main(
        [
            "download",
            "https://www.bilimanga.net/read/285/24327.html",
            "--output",
            str(tmp_path),
            "--format",
            "cbz",
        ]
    )

    output = capsys.readouterr().out
    assert result == 1
    assert "conversion failed" in output
    assert "Chapter: conversion failed: bad image" in output


def test_download_command_can_package_by_volume(monkeypatch, tmp_path: Path) -> None:
    class VolumeClient(FakeClient):
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
            del url, chapter_limit, image_limit, chapters_selection, chapter_filters, chapter_concurrency
            chapter_1 = self.output_dir / "Series" / "第１卷 STAGE.１"
            chapter_2 = self.output_dir / "Series" / "第１卷 STAGE.２"
            chapter_1.mkdir(parents=True)
            chapter_2.mkdir(parents=True)
            for chapter_dir in (chapter_1, chapter_2):
                (chapter_dir / ".complete").touch()
                (chapter_dir / "001.jpg").write_bytes(b"\xff\xd8")
            return DownloadSummary(
                series_title="Series",
                total_chapters=2,
                total_images=2,
                downloaded=2,
                skipped=0,
                output_dir=self.output_dir,
                chapters=(
                    DownloadedChapter(title="第１卷 STAGE.１", volume_title="第１卷", chapter_dir=chapter_1),
                    DownloadedChapter(title="第１卷 STAGE.２", volume_title="第１卷", chapter_dir=chapter_2),
                ),
            )

    monkeypatch.setattr(cli, "BilimangaClient", VolumeClient)

    result = cli.main(
        [
            "download",
            "https://www.bilimanga.net/detail/285.html",
            "--output",
            str(tmp_path),
            "--format",
            "cbz",
            "--package",
            "volume",
        ]
    )

    assert result == 0
    assert (tmp_path / "Series" / "第１卷.cbz").exists()
    assert not (tmp_path / "Series" / "第１卷 STAGE.１.cbz").exists()


def test_volume_package_with_pdf_format_reports_conversion_issue(tmp_path: Path) -> None:
    summary = DownloadSummary(
        series_title="Series",
        total_chapters=1,
        total_images=1,
        downloaded=1,
        skipped=0,
        output_dir=tmp_path,
    )

    issues = cli._convert_downloaded_chapters(summary, fmt="pdf", package_mode="volume", optimize=False)

    assert len(issues) == 1
    assert issues[0].chapter_title == "Series"
    assert issues[0].kind == "conversion_failed"
    assert "Volume packaging only supports CBZ" in issues[0].message


def test_parse_chapter_selection_supports_all_ranges_and_lists() -> None:
    chapters = _chapters()

    assert cli.parse_chapter_selection("all", chapters) == chapters
    assert [chapter.chapter_id for chapter in cli.parse_chapter_selection("1,3", chapters)] == [1, 3]
    assert [chapter.chapter_id for chapter in cli.parse_chapter_selection("1-2", chapters)] == [1, 2]
    assert cli.parse_chapter_selection("999", chapters) == []


def test_apply_chapter_filters_supports_keep_exclude_undo_and_reset() -> None:
    chapters = _chapters()

    filtered = cli.apply_chapter_filters(chapters, ["+STAGE", "-再會"])
    assert [chapter.chapter_id for chapter in filtered] == [1]

    undone = cli.apply_chapter_filters(chapters, ["+STAGE", "-再會", "undo"])
    assert [chapter.chapter_id for chapter in undone] == [1, 2]

    reset = cli.apply_chapter_filters(chapters, ["+STAGE", "reset"])
    assert reset == chapters


def test_info_command_prints_series_metadata(monkeypatch, capsys) -> None:
    async def fake_info(url: str) -> SimpleNamespace:
        assert url == "285"
        return SimpleNamespace(title="新世紀福音戰士 完全版", chapters=_chapters(), url="https://example")

    monkeypatch.setattr(cli, "_load_series_info", fake_info)

    assert cli.main(["info", "285"]) == 0
    assert "新世紀福音戰士 完全版" in capsys.readouterr().out


def test_list_and_clean_commands_use_cleanup_helpers(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(cli.SettingsRepository, "load", lambda self: Settings(output_dir=str(tmp_path)))
    monkeypatch.setattr(
        cli,
        "list_downloaded_series",
        lambda output_dir: [SimpleNamespace(name="Series", completed_chapters=1, total_size_bytes=1024)],
    )
    monkeypatch.setattr(
        cli,
        "build_cleanup_plan",
        lambda output_dir: SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    path=tmp_path / "Series" / "Chapter",
                    size_bytes=512,
                    relative_path=Path("Series/Chapter"),
                )
            ],
            total_size_bytes=512,
        ),
    )
    monkeypatch.setattr(cli, "apply_cleanup_plan", lambda plan: SimpleNamespace(removed_count=1, failed=[]))

    assert cli.main(["list"]) == 0
    assert cli.main(["clean", "--force"]) == 0
    output = capsys.readouterr().out
    assert "Series" in output
    assert "Removed 1" in output


def test_history_command_lists_and_clears_entries(monkeypatch, capsys) -> None:
    class FakeHistoryRepository:
        cleared = False

        def list_entries(self) -> list[HistoryEntry]:
            return [
                HistoryEntry(
                    timestamp="2026-05-16T00:00:00Z",
                    title="Series",
                    chapters_count=2,
                    format="pdf",
                    completed=2,
                )
            ]

        def clear(self) -> None:
            FakeHistoryRepository.cleared = True

    monkeypatch.setattr(cli, "HistoryRepository", FakeHistoryRepository)

    assert cli.main(["history"]) == 0
    assert "Series" in capsys.readouterr().out
    assert cli.main(["history", "clear"]) == 0
    assert FakeHistoryRepository.cleared is True


def test_settings_command_prints_current_settings(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        cli.SettingsRepository,
        "load",
        lambda self: Settings(output_dir=str(tmp_path), default_format="cbz"),
    )

    assert cli.main(["settings"]) == 0
    output = capsys.readouterr().out
    assert str(tmp_path) in output
    assert "cbz" in output


def test_doctor_checks_runtime_dependencies(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(cli.SettingsRepository, "load", lambda self: Settings(output_dir=str(tmp_path)))
    monkeypatch.setattr(cli, "detect_chrome_path", lambda: str(tmp_path / "chrome"))
    (tmp_path / "chrome").write_text("chrome", encoding="utf-8")

    result = cli.main(["doctor"])

    assert result == 0
    output = capsys.readouterr().out
    assert "Python" in output
    assert "bilimanga URL probe" in output
