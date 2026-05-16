from __future__ import annotations

import json
from typing import TYPE_CHECKING

from bilimanga_dl.core.history import (
    MAX_ENTRIES,
    HistoryEntry,
    HistoryRepository,
    clear_history,
    list_history,
    record_download,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_record_download_persists_counts_summary_and_issues(tmp_path: Path) -> None:
    repository = HistoryRepository(tmp_path / "history.json")

    repository.record_download(
        "新世紀福音戰士 完全版",
        3,
        "both",
        total_size_bytes=2048,
        completed=1,
        skipped=1,
        partial=1,
        failed=0,
        summary_text="1 downloaded, 1 skipped, 1 partial",
        issues=["STAGE.２: 1 image failed"],
    )

    entries = repository.list_entries()
    assert len(entries) == 1
    assert entries[0].title == "新世紀福音戰士 完全版"
    assert entries[0].completed == 1
    assert entries[0].skipped == 1
    assert entries[0].partial == 1
    assert entries[0].failed == 0
    assert entries[0].summary_text == "1 downloaded, 1 skipped, 1 partial"
    assert entries[0].issues == ["STAGE.２: 1 image failed"]


def test_history_repository_lists_newest_first_and_trims(tmp_path: Path) -> None:
    repository = HistoryRepository(tmp_path / "history.json", max_entries=2)

    repository.record_download("A", 1, "pdf")
    repository.record_download("B", 1, "pdf")
    repository.record_download("C", 1, "pdf")

    assert [entry.title for entry in repository.list_entries()] == ["C", "B"]


def test_history_repository_skips_malformed_entries(tmp_path: Path) -> None:
    history_file = tmp_path / "history.json"
    history_file.write_text(
        json.dumps(
            [
                {"timestamp": "2024-01-01T00:00:00Z", "title": "Good", "chapters_count": 1, "format": "pdf"},
                {"bad": "entry"},
            ]
        ),
        encoding="utf-8",
    )

    entries = HistoryRepository(history_file).list_entries()

    assert entries == [HistoryEntry(timestamp="2024-01-01T00:00:00Z", title="Good", chapters_count=1, format="pdf")]


def test_history_repository_handles_corrupt_json(tmp_path: Path) -> None:
    history_file = tmp_path / "history.json"
    history_file.write_text("broken", encoding="utf-8")

    assert HistoryRepository(history_file).list_entries() == []


def test_default_history_wrappers_use_default_repository(monkeypatch, tmp_path: Path) -> None:
    history_file = tmp_path / "history.json"
    monkeypatch.setattr("bilimanga_dl.core.history._HISTORY_FILE", history_file)

    record_download("Title", 1, "pdf")
    assert list_history()[0].title == "Title"
    clear_history()
    assert not history_file.exists()


def test_history_max_entries_constant_is_positive() -> None:
    assert MAX_ENTRIES > 0
