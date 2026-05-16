from __future__ import annotations

from bilimanga_dl.core.models import ChapterInfo, chapter_number_sort_key, normalize_chapter_number


def test_normalize_chapter_number_preserves_user_meaningful_values() -> None:
    assert normalize_chapter_number(" 10.5 ") == "10.5"
    assert normalize_chapter_number(12) == "12"
    assert normalize_chapter_number(3.5) == "3.5"
    assert normalize_chapter_number(None) == "0"


def test_chapter_number_sort_key_sorts_naturally() -> None:
    chapters = [
        ChapterInfo(title="Chapter 10", chapter_id=10, number="10"),
        ChapterInfo(title="Chapter 2", chapter_id=2, number="2"),
        ChapterInfo(title="Chapter 10.5", chapter_id=105, number="10.5"),
    ]

    ordered = sorted(chapters, key=lambda chapter: chapter.number_sort_key)

    assert [chapter.number for chapter in ordered] == ["2", "10", "10.5"]
    assert chapter_number_sort_key("2") < chapter_number_sort_key("10")
