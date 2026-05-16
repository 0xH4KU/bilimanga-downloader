from __future__ import annotations

from typing import TYPE_CHECKING

from bilimanga_dl.core.cleanup import apply_cleanup_plan, build_cleanup_plan, list_downloaded_series

if TYPE_CHECKING:
    from pathlib import Path


def test_list_downloaded_series_counts_completed_chapters_and_outputs(tmp_path: Path) -> None:
    chapter_dir = tmp_path / "Series" / "Chapter 1"
    chapter_dir.mkdir(parents=True)
    (chapter_dir / ".complete").touch()
    (chapter_dir.parent / "Chapter 1.pdf").write_bytes(b"x" * 2048)

    (tmp_path / "Empty").mkdir()

    result = list_downloaded_series(tmp_path)

    assert [item.name for item in result] == ["Series"]
    assert result[0].completed_chapters == 1
    assert result[0].total_size_bytes == 2048


def test_cleanup_plan_includes_only_complete_chapters_with_converted_output(tmp_path: Path) -> None:
    kept_dir = tmp_path / "Series" / "Chapter 1"
    kept_dir.mkdir(parents=True)
    (kept_dir / ".complete").touch()
    (kept_dir / "001.jpg").write_bytes(b"image")
    (kept_dir.parent / "Chapter 1.cbz").write_bytes(b"archive")

    partial_dir = tmp_path / "Series" / "Chapter 2"
    partial_dir.mkdir()
    (partial_dir / "chapter.state.json").write_text("{}", encoding="utf-8")
    (partial_dir.parent / "Chapter 2.cbz").write_bytes(b"archive")

    no_output_dir = tmp_path / "Series" / "Chapter 3"
    no_output_dir.mkdir()
    (no_output_dir / ".complete").touch()

    plan = build_cleanup_plan(tmp_path)

    assert [candidate.relative_path.as_posix() for candidate in plan.candidates] == ["Series/Chapter 1"]
    assert plan.total_size_bytes == len(b"image")


def test_cleanup_plan_can_scope_to_one_series(tmp_path: Path) -> None:
    scoped_dir = tmp_path / "Series Special" / "Chapter 1"
    scoped_dir.mkdir(parents=True)
    (scoped_dir / ".complete").touch()
    (scoped_dir.parent / "Chapter 1.pdf").write_bytes(b"pdf")

    other_dir = tmp_path / "Other" / "Chapter 1"
    other_dir.mkdir(parents=True)
    (other_dir / ".complete").touch()
    (other_dir.parent / "Chapter 1.pdf").write_bytes(b"pdf")

    plan = build_cleanup_plan(tmp_path, series_title="Series: Special")

    assert [candidate.relative_path.as_posix() for candidate in plan.candidates] == ["Series Special/Chapter 1"]


def test_apply_cleanup_plan_removes_candidate_directories(tmp_path: Path) -> None:
    chapter_dir = tmp_path / "Series" / "Chapter 1"
    chapter_dir.mkdir(parents=True)
    (chapter_dir / ".complete").touch()
    (chapter_dir / "001.jpg").write_bytes(b"image")
    (chapter_dir.parent / "Chapter 1.pdf").write_bytes(b"pdf")

    plan = build_cleanup_plan(tmp_path)
    result = apply_cleanup_plan(plan)

    assert result.removed_count == 1
    assert result.failed == []
    assert not chapter_dir.exists()
