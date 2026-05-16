from __future__ import annotations

from bilimanga_dl.sites.bilimanga import BilimangaParser


def test_parse_detail_url() -> None:
    parser = BilimangaParser("https://www.bilimanga.net")

    parsed = parser.parse_url("https://www.bilimanga.net/detail/285.html")

    assert parsed.kind == "series"
    assert parsed.manga_id == 285
    assert parsed.volume_id is None
    assert parsed.chapter_id is None


def test_parse_volume_url() -> None:
    parser = BilimangaParser("https://www.bilimanga.net")

    parsed = parser.parse_url("https://www.bilimanga.net/detail/285/vol_24326.html")

    assert parsed.kind == "volume"
    assert parsed.manga_id == 285
    assert parsed.volume_id == 24326
    assert parsed.chapter_id is None


def test_parse_reader_url() -> None:
    parser = BilimangaParser("https://www.bilimanga.net")

    parsed = parser.parse_url("https://www.bilimanga.net/read/285/24327.html")

    assert parsed.kind == "chapter"
    assert parsed.manga_id == 285
    assert parsed.volume_id is None
    assert parsed.chapter_id == 24327


def test_parse_rejects_other_hosts() -> None:
    parser = BilimangaParser("https://www.bilimanga.net")

    parsed = parser.parse_url("https://example.com/detail/285.html")

    assert parsed.kind == "unknown"
