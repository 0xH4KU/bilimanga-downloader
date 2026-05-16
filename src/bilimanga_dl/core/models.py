"""Shared data models used by parser, adapters, client, and CLI."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedUrl:
    """A normalized bilimanga URL classification."""

    kind: str
    manga_id: int | None = None
    volume_id: int | None = None
    chapter_id: int | None = None


@dataclass
class Chapter:
    """One readable chapter."""

    manga_id: int
    chapter_id: int
    title: str
    url: str
    series_title: str = ""
    volume_title: str = ""
    image_urls: list[str] = field(default_factory=list)


@dataclass
class Volume:
    """One collected volume page, containing chapter links when hydrated."""

    manga_id: int
    volume_id: int
    title: str
    url: str
    chapters: list[Chapter] = field(default_factory=list)


@dataclass
class Series:
    """Top-level manga metadata."""

    manga_id: int
    title: str
    url: str
    authors: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    description: str = ""
    volumes: list[Volume] = field(default_factory=list)


def normalize_chapter_number(raw_number: object) -> str:
    """Coerce a remote chapter number into a stable string."""
    if isinstance(raw_number, str):
        normalized = raw_number.strip()
    elif isinstance(raw_number, int):
        normalized = str(raw_number)
    elif isinstance(raw_number, float):
        normalized = format(raw_number, "g")
    else:
        normalized = "0"
    return normalized or "0"


def chapter_number_sort_key(number: str) -> tuple[tuple[int, str], ...]:
    """Build a stable natural-sort key for chapter labels."""
    tokens = re.findall(r"\d+|[^\d]+", number.lower())
    key: list[tuple[int, str]] = []
    for token in tokens:
        if token.isdigit():
            key.append((0, token.zfill(12)))
            continue
        cleaned = re.sub(r"[^a-z]+", "", token)
        if cleaned:
            key.append((1, cleaned))
    return tuple(key) or ((0, "000000000000"),)


@dataclass
class SearchResult:
    """A single search result returned by a site adapter."""

    title: str
    url: str
    slug: str
    hash_id: str


@dataclass
class ChapterInfo:
    """Framework-level chapter metadata."""

    title: str
    chapter_id: int
    number: str
    name: str = ""
    language: str = "zh"
    image_count: int = 0
    number_sort_key: tuple[tuple[int, str], ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.number = normalize_chapter_number(self.number)
        self.number_sort_key = chapter_number_sort_key(self.number)


@dataclass
class ChapterImages:
    """Resolved image URLs for a single chapter."""

    title: str
    chapter_label: str
    image_urls: list[str]


@dataclass
class DedupDecision:
    """Human-readable explanation of a chapter deduplication decision."""

    chapter_number: str
    reason: str
    kept: tuple[str, ...]
    dropped: tuple[str, ...]


@dataclass
class SeriesInfo:
    """Framework-level series metadata."""

    title: str
    authors: list[str]
    genres: list[str]
    description: str
    chapters: list[ChapterInfo]
    url: str
    hash_id: str
    dedup_decisions: list[DedupDecision] = field(default_factory=list)
