"""Local download verification against expected bilimanga chapters."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from bilimanga_dl.core.converters import collect_images
from bilimanga_dl.core.downloader import sanitize_dirname

if TYPE_CHECKING:
    from pathlib import Path

    from bilimanga_dl.core.models import Chapter

_META_FILE = "chapter.meta.json"
_COMPLETE_MARKER = ".complete"
_STATE_FILE = "chapter.state.json"
_VOLUME_PREFIX_RE = re.compile(r"^第[\uff10-\uff190-9一二三四五六七八九十]+卷\s+")


class VerifyStatus(StrEnum):
    """Verification status for one expected chapter."""

    COMPLETE = "complete"
    MISSING = "missing"
    INCOMPLETE = "incomplete"
    IMAGE_MISMATCH = "image_mismatch"


@dataclass(frozen=True)
class ExpectedChapter:
    """Expected remote chapter plus optional resolved image count."""

    chapter: Chapter
    expected_image_count: int | None = None


@dataclass(frozen=True)
class LocalChapter:
    """Local chapter directory and metadata used for matching."""

    path: Path
    title: str
    normalized_title: str
    chapter_id: int | None
    expected_image_count: int | None
    image_count: int
    complete: bool
    has_state: bool


@dataclass(frozen=True)
class VerifyItem:
    """Verification result for one expected chapter."""

    chapter: Chapter
    status: VerifyStatus
    local_dir: Path | None = None
    expected_image_count: int | None = None
    local_image_count: int = 0
    message: str = ""


@dataclass(frozen=True)
class VerifyReport:
    """Aggregate verification result."""

    series_title: str
    output_dir: Path
    items: tuple[VerifyItem, ...]
    extra_local_dirs: tuple[Path, ...] = ()

    @property
    def total_expected(self) -> int:
        return len(self.items)

    @property
    def completed_count(self) -> int:
        return sum(1 for item in self.items if item.status == VerifyStatus.COMPLETE)

    @property
    def missing_count(self) -> int:
        return sum(1 for item in self.items if item.status == VerifyStatus.MISSING)

    @property
    def incomplete_count(self) -> int:
        return sum(1 for item in self.items if item.status in {VerifyStatus.INCOMPLETE, VerifyStatus.IMAGE_MISMATCH})

    @property
    def ok(self) -> bool:
        return self.missing_count == 0 and self.incomplete_count == 0

    @property
    def repair_chapters(self) -> tuple[Chapter, ...]:
        return tuple(item.chapter for item in self.items if item.status != VerifyStatus.COMPLETE)


def build_verify_report(
    series_title: str,
    expected_chapters: list[ExpectedChapter],
    output_dir: Path,
) -> VerifyReport:
    """Compare expected remote chapters with local downloaded chapter directories."""
    series_dir = output_dir / sanitize_dirname(series_title)
    local_chapters = _index_local_chapters(series_dir)
    by_id = {chapter.chapter_id: chapter for chapter in local_chapters if chapter.chapter_id is not None}
    by_title = {chapter.normalized_title: chapter for chapter in local_chapters}

    matched_dirs: set[Path] = set()
    items: list[VerifyItem] = []
    for expected in expected_chapters:
        chapter = expected.chapter
        local = by_id.get(chapter.chapter_id) or by_title.get(normalize_chapter_title(chapter.title))
        if local is None:
            items.append(
                VerifyItem(
                    chapter=chapter,
                    status=VerifyStatus.MISSING,
                    expected_image_count=expected.expected_image_count,
                    message="chapter directory not found",
                )
            )
            continue

        matched_dirs.add(local.path)
        expected_image_count = expected.expected_image_count
        if expected_image_count is None:
            expected_image_count = local.expected_image_count
        items.append(_verify_local_chapter(chapter, expected_image_count, local))

    extra_dirs = tuple(chapter.path for chapter in local_chapters if chapter.path not in matched_dirs)
    return VerifyReport(
        series_title=series_title,
        output_dir=output_dir,
        items=tuple(items),
        extra_local_dirs=extra_dirs,
    )


def normalize_chapter_title(title: str) -> str:
    """Normalize reader and volume-list chapter titles for legacy directory matching."""
    cleaned = title.strip()
    cleaned = _VOLUME_PREFIX_RE.sub("", cleaned)
    cleaned = cleaned.replace("...", "⋯⋯").replace("\uff0e", ".")
    cleaned = cleaned.rstrip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.casefold()


def _verify_local_chapter(chapter: Chapter, expected_image_count: int | None, local: LocalChapter) -> VerifyItem:
    if local.has_state or not local.complete:
        return VerifyItem(
            chapter=chapter,
            status=VerifyStatus.INCOMPLETE,
            local_dir=local.path,
            expected_image_count=expected_image_count,
            local_image_count=local.image_count,
            message="chapter is not marked complete",
        )
    if expected_image_count is not None and local.image_count != expected_image_count:
        return VerifyItem(
            chapter=chapter,
            status=VerifyStatus.IMAGE_MISMATCH,
            local_dir=local.path,
            expected_image_count=expected_image_count,
            local_image_count=local.image_count,
            message=f"expected {expected_image_count} image(s), found {local.image_count}",
        )
    return VerifyItem(
        chapter=chapter,
        status=VerifyStatus.COMPLETE,
        local_dir=local.path,
        expected_image_count=expected_image_count,
        local_image_count=local.image_count,
    )


def _index_local_chapters(series_dir: Path) -> list[LocalChapter]:
    if not series_dir.exists():
        return []
    return [
        _read_local_chapter(path)
        for path in sorted(series_dir.iterdir())
        if path.is_dir()
    ]


def _read_local_chapter(path: Path) -> LocalChapter:
    metadata = _read_metadata(path / _META_FILE)
    title = _metadata_text(metadata, "title") or path.name
    chapter_id = _metadata_int(metadata, "chapter_id")
    return LocalChapter(
        path=path,
        title=title,
        normalized_title=normalize_chapter_title(title or path.name),
        chapter_id=chapter_id,
        expected_image_count=_metadata_int(metadata, "expected_image_count"),
        image_count=len(collect_images(path)),
        complete=(path / _COMPLETE_MARKER).exists(),
        has_state=(path / _STATE_FILE).exists(),
    )


def _read_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _metadata_text(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    return value if isinstance(value, str) else ""


def _metadata_int(metadata: dict[str, Any], key: str) -> int | None:
    value = metadata.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
