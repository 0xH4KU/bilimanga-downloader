"""Shared data models used by the parser, client, and CLI."""

from __future__ import annotations

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
