"""Formatting helpers for download summaries and issue reporting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bilimanga_dl.core.client import DownloadSummary


@dataclass(frozen=True)
class DownloadIssue:
    """User-facing issue associated with one chapter."""

    chapter_title: str
    kind: str
    message: str


@dataclass(frozen=True)
class DownloadReport:
    """Formatted download summary shared by CLI, history, and notifications."""

    summary_text: str
    size_text: str
    issue_lines: tuple[str, ...]
    notification_body: str

    def preview_issue_lines(self, *, max_lines: int = 5) -> tuple[str, ...]:
        """Return a bounded issue preview."""
        if len(self.issue_lines) <= max_lines:
            return self.issue_lines
        hidden = len(self.issue_lines) - max_lines
        return (*self.issue_lines[:max_lines], f"... and {hidden} more issue(s)")


def format_bytes(n: int) -> str:
    """Format bytes in a human-readable unit."""
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_download_counts(*, completed: int, skipped: int, partial: int, failed: int) -> str:
    """Return a stable textual summary of result counts."""
    parts: list[str] = []
    if completed:
        parts.append(f"{completed} downloaded")
    if skipped:
        parts.append(f"{skipped} skipped")
    if partial:
        parts.append(f"{partial} partial")
    if failed:
        parts.append(f"{failed} failed")
    return ", ".join(parts) if parts else "Nothing to do"


def build_download_report(summary: DownloadSummary) -> DownloadReport:
    """Build a report from a download summary."""
    summary_text = format_download_counts(
        completed=summary.downloaded,
        skipped=summary.skipped,
        partial=summary.partial,
        failed=summary.failed,
    )
    size_text = format_bytes(summary.total_bytes)
    issue_lines = tuple(f"{issue.chapter_title}: {issue.message}" for issue in summary.issues)
    notification_body = f"{summary_text} ({size_text})"
    if issue_lines:
        notification_body += f" | {issue_lines[0]}"
        if len(issue_lines) > 1:
            notification_body += f" | +{len(issue_lines) - 1} more issue(s)"

    return DownloadReport(
        summary_text=summary_text,
        size_text=size_text,
        issue_lines=issue_lines,
        notification_body=notification_body,
    )
