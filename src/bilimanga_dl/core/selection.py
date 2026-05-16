"""Chapter selection and keyword filter helpers."""

from __future__ import annotations

from typing import Protocol, TypeVar


class TitledChapter(Protocol):
    """Minimal protocol for objects that can be keyword-filtered."""

    title: str


T = TypeVar("T")
TChapter = TypeVar("TChapter", bound=TitledChapter)


def parse_chapter_selection(selection: str, chapters: list[T]) -> list[T]:
    """Parse ``all``, ``1``, ``1-5``, or ``1,3,5`` against chapter order."""
    if selection.strip().lower() == "all":
        return list(chapters)

    indices: set[int] = set()
    for part in selection.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            try:
                start, end = token.split("-", 1)
                for index in range(int(start.strip()), int(end.strip()) + 1):
                    indices.add(index)
            except ValueError:
                continue
            continue
        try:
            indices.add(int(token))
        except ValueError:
            continue

    return [chapters[index - 1] for index in sorted(indices) if 1 <= index <= len(chapters)]


def apply_chapter_filters(chapters: list[TChapter], filters: list[str]) -> list[TChapter]:
    """Apply ``+keyword`` / ``-keyword`` filters with undo/reset commands."""
    filtered = list(chapters)
    history: list[list[TChapter]] = []
    for raw_filter in filters:
        command = raw_filter.strip()
        if not command:
            continue
        lowered = command.lower()
        if lowered in {"undo", "u"}:
            if history:
                filtered = history.pop()
            continue
        if lowered in {"reset", "r"}:
            history.append(filtered)
            filtered = list(chapters)
            continue

        keep_words = [token[1:].lower() for token in command.split() if token.startswith("+") and token[1:]]
        remove_words = [token[1:].lower() for token in command.split() if token.startswith("-") and token[1:]]
        bare_words = [token.lower() for token in command.split() if not token.startswith(("+", "-"))]
        keep_words.extend(bare_words)
        if not keep_words and not remove_words:
            continue

        history.append(filtered)
        if keep_words:
            filtered = [chapter for chapter in filtered if any(word in chapter.title.lower() for word in keep_words)]
        if remove_words:
            filtered = [
                chapter for chapter in filtered if not any(word in chapter.title.lower() for word in remove_words)
            ]
    return filtered
