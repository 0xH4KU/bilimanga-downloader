from __future__ import annotations

from typing import TYPE_CHECKING

from bilimanga_dl.core.models import Chapter
from bilimanga_dl.core.verify import (
    ExpectedChapter,
    VerifyStatus,
    build_verify_report,
    normalize_chapter_title,
)

if TYPE_CHECKING:
    from pathlib import Path


def _chapter(title: str, chapter_id: int, image_count: int = 2) -> ExpectedChapter:
    return ExpectedChapter(
        chapter=Chapter(
            manga_id=285,
            chapter_id=chapter_id,
            title=title,
            url=f"https://www.bilimanga.net/read/285/{chapter_id}.html",
            volume_title="新世紀福音戰士 完全版 1",
        ),
        expected_image_count=image_count,
    )


def test_normalize_chapter_title_removes_reader_volume_prefix_and_minor_punctuation() -> None:
    assert normalize_chapter_title("第１卷 STAGE.49 ⋯⋯Kiss.") == normalize_chapter_title("STAGE.49 ⋯⋯Kiss")
    assert normalize_chapter_title("第2卷  STAGE.62 distance") == "stage.62 distance"


def test_build_verify_report_detects_missing_in_legacy_download_dir(tmp_path: Path) -> None:
    series_dir = tmp_path / "新世紀福音戰士 完全版"
    chapter_dir = series_dir / "第１卷 STAGE.１ 使徒、來襲"
    chapter_dir.mkdir(parents=True)
    (chapter_dir / ".complete").touch()
    (chapter_dir / "001.jpg").write_bytes(b"\xff\xd8")
    (chapter_dir / "002.jpg").write_bytes(b"\xff\xd8")

    report = build_verify_report(
        "新世紀福音戰士 完全版",
        [_chapter("STAGE.１ 使徒、來襲", 24327), _chapter("STAGE.８ 真嗣不高興了", 24334)],
        tmp_path,
    )

    assert report.total_expected == 2
    assert report.completed_count == 1
    assert report.missing_count == 1
    assert [item.chapter.title for item in report.items if item.status == VerifyStatus.MISSING] == [
        "STAGE.８ 真嗣不高興了"
    ]


def test_build_verify_report_detects_image_count_mismatch(tmp_path: Path) -> None:
    series_dir = tmp_path / "新世紀福音戰士 完全版"
    chapter_dir = series_dir / "第１卷 STAGE.１ 使徒、來襲"
    chapter_dir.mkdir(parents=True)
    (chapter_dir / ".complete").touch()
    (chapter_dir / "001.jpg").write_bytes(b"\xff\xd8")

    report = build_verify_report("新世紀福音戰士 完全版", [_chapter("STAGE.１ 使徒、來襲", 24327, 2)], tmp_path)

    assert report.incomplete_count == 1
    assert report.items[0].status == VerifyStatus.IMAGE_MISMATCH
    assert report.items[0].local_image_count == 1
    assert report.items[0].expected_image_count == 2


def test_build_verify_report_prefers_chapter_metadata_over_legacy_name_matching(tmp_path: Path) -> None:
    series_dir = tmp_path / "新世紀福音戰士 完全版"
    chapter_dir = series_dir / "old title"
    chapter_dir.mkdir(parents=True)
    (chapter_dir / ".complete").touch()
    (chapter_dir / "001.jpg").write_bytes(b"\xff\xd8")
    (chapter_dir / "chapter.meta.json").write_text(
        '{"chapter_id": 24327, "title": "STAGE.１ 使徒、來襲", "expected_image_count": 1}',
        encoding="utf-8",
    )

    report = build_verify_report("新世紀福音戰士 完全版", [_chapter("STAGE.１ 使徒、來襲", 24327, 1)], tmp_path)

    assert report.completed_count == 1
    assert report.items[0].local_dir == chapter_dir


def test_build_verify_report_uses_local_metadata_image_count_when_remote_count_not_refreshed(tmp_path: Path) -> None:
    series_dir = tmp_path / "新世紀福音戰士 完全版"
    chapter_dir = series_dir / "第１卷 STAGE.１ 使徒、來襲"
    chapter_dir.mkdir(parents=True)
    (chapter_dir / ".complete").touch()
    (chapter_dir / "001.jpg").write_bytes(b"\xff\xd8")
    (chapter_dir / "chapter.meta.json").write_text(
        '{"chapter_id": 24327, "title": "STAGE.１ 使徒、來襲", "expected_image_count": 2}',
        encoding="utf-8",
    )

    report = build_verify_report(
        "新世紀福音戰士 完全版",
        [ExpectedChapter(chapter=_chapter("STAGE.１ 使徒、來襲", 24327).chapter)],
        tmp_path,
    )

    assert report.items[0].status == VerifyStatus.IMAGE_MISMATCH
    assert report.items[0].expected_image_count == 2
    assert report.items[0].local_image_count == 1


def test_build_verify_report_lists_extra_local_directories(tmp_path: Path) -> None:
    series_dir = tmp_path / "新世紀福音戰士 完全版"
    extra_dir = series_dir / "第１卷 UNUSED"
    extra_dir.mkdir(parents=True)
    (extra_dir / ".complete").touch()

    report = build_verify_report("新世紀福音戰士 完全版", [_chapter("STAGE.１ 使徒、來襲", 24327)], tmp_path)

    assert report.extra_local_dirs == (extra_dir,)
