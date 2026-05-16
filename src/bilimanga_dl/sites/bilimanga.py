"""bilimanga.net HTML parser.

The site exposes ordinary HTML for series and volume pages. Reader
pages render chapter image tags only in a real mobile-browser shaped
environment, but the resulting HTML still contains plain image URLs.
This module owns the site-specific URL shapes and DOM extraction rules.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from bilimanga_dl.core.models import Chapter, ParsedUrl, Series, Volume

_DETAIL_RE = re.compile(r"^/detail/(?P<manga>\d+)\.html$")
_VOLUME_RE = re.compile(r"^/detail/(?P<manga>\d+)/vol_(?P<volume>\d+)\.html$")
_READ_RE = re.compile(r"^/read/(?P<manga>\d+)/(?P<chapter>\d+)\.html$")
_READ_PARAMS_FIELD_RE = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*'(?P<value>[^']*)'")


class BilimangaParser:
    """Parse bilimanga URLs and HTML pages."""

    def __init__(self, base_url: str = "https://www.bilimanga.net") -> None:
        self.base_url = base_url.rstrip("/")
        self.host = urlparse(self.base_url).hostname or "www.bilimanga.net"

    def parse_url(self, url: str) -> ParsedUrl:
        """Classify a bilimanga URL."""
        try:
            parsed = urlparse(url.strip())
        except ValueError:
            return ParsedUrl(kind="unknown")
        if parsed.hostname != self.host:
            return ParsedUrl(kind="unknown")

        if match := _DETAIL_RE.match(parsed.path):
            return ParsedUrl(kind="series", manga_id=int(match.group("manga")))
        if match := _VOLUME_RE.match(parsed.path):
            return ParsedUrl(
                kind="volume",
                manga_id=int(match.group("manga")),
                volume_id=int(match.group("volume")),
            )
        if match := _READ_RE.match(parsed.path):
            return ParsedUrl(
                kind="chapter",
                manga_id=int(match.group("manga")),
                chapter_id=int(match.group("chapter")),
            )
        return ParsedUrl(kind="unknown")

    def parse_series_detail(self, html: str, url: str) -> Series:
        """Extract series metadata and volume links from a detail page."""
        parsed_url = self.parse_url(url)
        if parsed_url.manga_id is None:
            raise ValueError(f"Not a bilimanga detail URL: {url}")

        soup = BeautifulSoup(html, "html.parser")
        title = _text_one(soup, ".book-title") or str(parsed_url.manga_id)
        series = Series(
            manga_id=parsed_url.manga_id,
            title=title,
            url=url,
            authors=_unique_texts(soup.select(".authorname a, .illname a")),
            genres=_unique_texts(soup.select(".tag-small-group.origin-left a.tag-small")),
            description=_summary_text(soup),
            volumes=self._parse_volume_links(soup, parsed_url.manga_id),
        )
        series.volumes.sort(key=lambda volume: _natural_key(volume.title))
        return series

    def parse_volume(self, html: str, url: str) -> Volume:
        """Extract chapter links from a volume page."""
        parsed_url = self.parse_url(url)
        if parsed_url.manga_id is None or parsed_url.volume_id is None:
            raise ValueError(f"Not a bilimanga volume URL: {url}")

        soup = BeautifulSoup(html, "html.parser")
        title = _text_one(soup, ".book-title") or str(parsed_url.volume_id)
        volume = Volume(
            manga_id=parsed_url.manga_id,
            volume_id=parsed_url.volume_id,
            title=title,
            url=url,
            chapters=self._parse_chapter_links(soup, parsed_url.manga_id),
        )
        return volume

    def parse_reader(self, html: str, url: str) -> Chapter:
        """Extract chapter image URLs from a rendered reader page."""
        parsed_url = self.parse_url(url)
        if parsed_url.manga_id is None or parsed_url.chapter_id is None:
            raise ValueError(f"Not a bilimanga reader URL: {url}")

        soup = BeautifulSoup(html, "html.parser")
        read_params = _extract_read_params(soup)
        title = read_params.get("chaptername") or _text_one(soup, "#atitle") or str(parsed_url.chapter_id)
        content = soup.select_one("#acontentz") or soup

        images: list[str] = []
        for img in content.select("img"):
            raw = _attr_one(img, "data-src") or _attr_one(img, "src")
            if not raw:
                continue
            image_url = urljoin(url, raw)
            host = urlparse(image_url).hostname or ""
            if "motiezw.com" not in host:
                continue
            if image_url not in images:
                images.append(image_url)

        return Chapter(
            manga_id=parsed_url.manga_id,
            chapter_id=parsed_url.chapter_id,
            title=title,
            url=url,
            series_title=read_params.get("manganame", ""),
            image_urls=images,
        )

    def _parse_volume_links(self, soup: BeautifulSoup, manga_id: int) -> list[Volume]:
        volumes: list[Volume] = []
        for link in soup.select(".volchapters a[href*='/detail/'][href*='vol_']"):
            href = _attr_one(link, "href")
            if not href:
                continue
            absolute = urljoin(self.base_url, href)
            parsed = self.parse_url(absolute)
            if parsed.manga_id != manga_id or parsed.volume_id is None:
                continue
            title = _text_one(link, "h3") or _clean_text(link.get_text(" "))
            if not title:
                title = f"Volume {parsed.volume_id}"
            volumes.append(Volume(manga_id=manga_id, volume_id=parsed.volume_id, title=title, url=absolute))
        return _dedupe_volumes(volumes)

    def _parse_chapter_links(self, soup: BeautifulSoup, manga_id: int) -> list[Chapter]:
        chapters: list[Chapter] = []
        for link in soup.select("li.chapter-li a[href*='/read/']"):
            href = _attr_one(link, "href")
            if not href:
                continue
            absolute = urljoin(self.base_url, href)
            parsed = self.parse_url(absolute)
            if parsed.manga_id != manga_id or parsed.chapter_id is None:
                continue
            title = _text_one(link, ".chapter-title") or _clean_text(link.get_text(" "))
            if not title:
                title = f"Chapter {parsed.chapter_id}"
            chapters.append(Chapter(manga_id=manga_id, chapter_id=parsed.chapter_id, title=title, url=absolute))
        return _dedupe_chapters(chapters)


def _text_one(scope: BeautifulSoup | Tag, selector: str) -> str:
    element = scope.select_one(selector)
    return _clean_text(element.get_text("\n")) if element else ""


def _attr_one(element: Tag, name: str) -> str:
    value = element.get(name)
    if isinstance(value, str):
        return value
    return ""


def _clean_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _unique_texts(elements: list[Tag]) -> list[str]:
    values: list[str] = []
    for element in elements:
        value = _clean_text(element.get_text(" "))
        if value and value not in values:
            values.append(value)
    return values


def _summary_text(soup: BeautifulSoup) -> str:
    content = soup.select_one("#bookSummary content")
    return _clean_text(content.get_text("\n")) if content else ""


def _natural_key(value: str) -> tuple[object, ...]:
    key: list[object] = []
    for token in re.findall(r"\d+|\D+", value):
        key.append(int(token) if token.isdigit() else token)
    return tuple(key)


def _dedupe_volumes(volumes: list[Volume]) -> list[Volume]:
    seen: set[int] = set()
    result: list[Volume] = []
    for volume in volumes:
        if volume.volume_id in seen:
            continue
        seen.add(volume.volume_id)
        result.append(volume)
    return result


def _dedupe_chapters(chapters: list[Chapter]) -> list[Chapter]:
    seen: set[int] = set()
    result: list[Chapter] = []
    for chapter in chapters:
        if chapter.chapter_id in seen:
            continue
        seen.add(chapter.chapter_id)
        result.append(chapter)
    return result


def _extract_read_params(soup: BeautifulSoup) -> dict[str, str]:
    for script in soup.find_all("script"):
        text = script.string or script.get_text("")
        if "ReadParams" not in text:
            continue
        return {match.group("key"): match.group("value") for match in _READ_PARAMS_FIELD_RE.finditer(text)}
    return {}
