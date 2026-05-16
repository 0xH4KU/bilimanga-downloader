"""Download listing and raw-image cleanup helpers."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bilimanga_dl.core.downloader import sanitize_dirname

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class DownloadedSeries:
    """Summary of one downloaded series directory."""

    name: str
    path: Path
    completed_chapters: int
    total_size_bytes: int


@dataclass(frozen=True)
class CleanupCandidate:
    """A raw image directory eligible for deletion."""

    path: Path
    relative_path: Path
    size_bytes: int


@dataclass(frozen=True)
class CleanupPlan:
    """Directories that can be safely cleaned."""

    output_dir: Path
    candidates: list[CleanupCandidate]
    total_size_bytes: int


@dataclass(frozen=True)
class CleanupResult:
    """Result of applying a cleanup plan."""

    removed_count: int
    failed: list[tuple[Path, str]]


def list_downloaded_series(output_dir: Path) -> list[DownloadedSeries]:
    """Summarize downloaded series under *output_dir*."""
    if not output_dir.exists():
        return []

    result: list[DownloadedSeries] = []
    for series_dir in sorted(output_dir.iterdir()):
        if not series_dir.is_dir():
            continue
        completed = sum(1 for item in series_dir.iterdir() if item.is_dir() and (item / ".complete").exists())
        output_size = sum(item.stat().st_size for item in series_dir.iterdir() if item.is_file())
        if completed == 0 and output_size == 0:
            continue
        result.append(
            DownloadedSeries(
                name=series_dir.name,
                path=series_dir,
                completed_chapters=completed,
                total_size_bytes=output_size,
            )
        )
    return result


def build_cleanup_plan(output_dir: Path, *, series_title: str | None = None) -> CleanupPlan:
    """Find complete raw image directories that already have converted outputs."""
    if not output_dir.exists():
        return CleanupPlan(output_dir=output_dir, candidates=[], total_size_bytes=0)

    if series_title is None:
        roots = [path for path in sorted(output_dir.iterdir()) if path.is_dir()]
    else:
        series_dir = output_dir / sanitize_dirname(series_title)
        roots = [series_dir] if series_dir.exists() and series_dir.is_dir() else []

    candidates: list[CleanupCandidate] = []
    total_size = 0
    for series_dir in roots:
        for chapter_dir in sorted(series_dir.iterdir()):
            if not chapter_dir.is_dir():
                continue
            if not _can_cleanup_chapter_dir(chapter_dir):
                continue
            size_bytes = sum(item.stat().st_size for item in chapter_dir.rglob("*") if item.is_file())
            candidates.append(
                CleanupCandidate(
                    path=chapter_dir,
                    relative_path=chapter_dir.relative_to(output_dir),
                    size_bytes=size_bytes,
                )
            )
            total_size += size_bytes

    return CleanupPlan(output_dir=output_dir, candidates=candidates, total_size_bytes=total_size)


def apply_cleanup_plan(plan: CleanupPlan) -> CleanupResult:
    """Delete every directory in a cleanup plan."""
    removed = 0
    failed: list[tuple[Path, str]] = []
    for candidate in plan.candidates:
        try:
            shutil.rmtree(candidate.path)
            removed += 1
        except OSError as exc:
            failed.append((candidate.path, str(exc)))
    return CleanupResult(removed_count=removed, failed=failed)


def _can_cleanup_chapter_dir(chapter_dir: Path) -> bool:
    if not (chapter_dir / ".complete").exists():
        return False
    if (chapter_dir / "chapter.state.json").exists():
        return False
    return (chapter_dir.parent / f"{chapter_dir.name}.pdf").exists() or (
        chapter_dir.parent / f"{chapter_dir.name}.cbz"
    ).exists()
