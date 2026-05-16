"""Download history storage."""

from __future__ import annotations

import contextlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from bilimanga_dl.core.fileio import atomic_write_text

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)

_HISTORY_FILE = Path.home() / ".config" / "bilimanga-dl" / "history.json"
MAX_ENTRIES = 500


@dataclass(frozen=True)
class HistoryEntry:
    """A single persisted download history record."""

    timestamp: str
    title: str
    chapters_count: int
    format: str
    total_size_bytes: int = 0
    completed: int = 0
    partial: int = 0
    failed: int = 0
    skipped: int = 0
    summary_text: str = ""
    issues: list[str] = field(default_factory=list)


class HistoryRepository:
    """Repository for reading and writing download history."""

    def __init__(self, history_file: Path | None = None, *, max_entries: int = MAX_ENTRIES) -> None:
        self._history_file = history_file or _HISTORY_FILE
        self._lock_file = self._history_file.with_suffix(".lock")
        self._max_entries = max_entries

    @contextlib.contextmanager
    def _file_lock(self) -> Iterator[None]:
        self._lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(str(self._lock_file), os.O_CREAT | os.O_RDWR)
        try:
            self._lock_fd(lock_fd)
            yield
        finally:
            self._unlock_fd(lock_fd)
            os.close(lock_fd)

    @staticmethod
    def _lock_fd(lock_fd: int) -> None:
        if os.name == "nt":
            import msvcrt

            if os.fstat(lock_fd).st_size == 0:
                os.write(lock_fd, b"\0")
                os.fsync(lock_fd)
            os.lseek(lock_fd, 0, os.SEEK_SET)
            msvcrt.locking(lock_fd, msvcrt.LK_LOCK, 1)  # type: ignore[attr-defined]
            return

        import fcntl

        fcntl.flock(lock_fd, fcntl.LOCK_EX)

    @staticmethod
    def _unlock_fd(lock_fd: int) -> None:
        if os.name == "nt":
            import msvcrt

            os.lseek(lock_fd, 0, os.SEEK_SET)
            msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
            return

        import fcntl

        fcntl.flock(lock_fd, fcntl.LOCK_UN)

    def record_download(
        self,
        title: str,
        chapters_count: int,
        fmt: str,
        total_size_bytes: int = 0,
        completed: int = 0,
        partial: int = 0,
        failed: int = 0,
        skipped: int = 0,
        summary_text: str = "",
        issues: list[str] | None = None,
    ) -> None:
        """Append one history entry and trim old records."""
        entry = HistoryEntry(
            timestamp=datetime.now(UTC).isoformat(),
            title=title,
            chapters_count=chapters_count,
            format=fmt,
            total_size_bytes=total_size_bytes,
            completed=completed,
            partial=partial,
            failed=failed,
            skipped=skipped,
            summary_text=summary_text,
            issues=list(issues or []),
        )
        with self._file_lock():
            entries = self._load_entries()
            entries.append(asdict(entry))
            if len(entries) > self._max_entries:
                entries = entries[-self._max_entries :]
            self._save_entries(entries)

    def list_entries(self) -> list[HistoryEntry]:
        """Return history entries newest first."""
        result: list[HistoryEntry] = []
        for data in reversed(self._load_entries()):
            entry = self._entry_from_mapping(data)
            if entry is None:
                continue
            result.append(entry)
        return result

    def clear(self) -> None:
        """Delete persisted history."""
        with contextlib.suppress(OSError):
            self._history_file.unlink()

    def _load_entries(self) -> list[dict[str, object]]:
        if not self._history_file.exists():
            return []
        try:
            data = json.loads(self._history_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load history: %s", exc)
            return []
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def _save_entries(self, entries: list[dict[str, object]]) -> None:
        atomic_write_text(self._history_file, json.dumps(entries, indent=2, ensure_ascii=False) + "\n")

    @staticmethod
    def _entry_from_mapping(data: dict[str, object]) -> HistoryEntry | None:
        try:
            timestamp = data["timestamp"]
            title = data["title"]
            chapters_count = data["chapters_count"]
            fmt = data["format"]
        except KeyError:
            return None
        if (
            not isinstance(timestamp, str)
            or not isinstance(title, str)
            or not isinstance(chapters_count, int)
            or not isinstance(fmt, str)
        ):
            return None

        return HistoryEntry(
            timestamp=timestamp,
            title=title,
            chapters_count=chapters_count,
            format=fmt,
            total_size_bytes=_int_or_default(data.get("total_size_bytes"), 0),
            completed=_int_or_default(data.get("completed"), 0),
            partial=_int_or_default(data.get("partial"), 0),
            failed=_int_or_default(data.get("failed"), 0),
            skipped=_int_or_default(data.get("skipped"), 0),
            summary_text=_str_or_default(data.get("summary_text"), ""),
            issues=_string_list(data.get("issues")),
        )


def _int_or_default(value: object, default: int) -> int:
    return value if isinstance(value, int) else default


def _str_or_default(value: object, default: str) -> str:
    return value if isinstance(value, str) else default


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def record_download(
    title: str,
    chapters_count: int,
    fmt: str,
    total_size_bytes: int = 0,
    completed: int = 0,
    partial: int = 0,
    failed: int = 0,
    skipped: int = 0,
    summary_text: str = "",
    issues: list[str] | None = None,
) -> None:
    """Record a download through the default repository."""
    HistoryRepository().record_download(
        title=title,
        chapters_count=chapters_count,
        fmt=fmt,
        total_size_bytes=total_size_bytes,
        completed=completed,
        partial=partial,
        failed=failed,
        skipped=skipped,
        summary_text=summary_text,
        issues=issues,
    )


def list_history() -> list[HistoryEntry]:
    """List entries from the default repository."""
    return HistoryRepository().list_entries()


def clear_history() -> None:
    """Clear the default history file."""
    HistoryRepository().clear()
