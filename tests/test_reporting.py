from __future__ import annotations

from pathlib import Path

from bilimanga_dl.core.client import DownloadSummary
from bilimanga_dl.core.reporting import (
    DownloadIssue,
    build_download_report,
    format_bytes,
    format_download_counts,
)


def test_format_download_counts_uses_stable_order() -> None:
    assert (
        format_download_counts(completed=2, skipped=1, partial=1, failed=0)
        == "2 downloaded, 1 skipped, 1 partial"
    )
    assert format_download_counts(completed=0, skipped=0, partial=0, failed=0) == "Nothing to do"


def test_format_bytes_uses_human_units() -> None:
    assert format_bytes(512) == "512.0 B"
    assert format_bytes(2048) == "2.0 KB"


def test_build_download_report_includes_issue_preview_and_notification_excerpt() -> None:
    summary = DownloadSummary(
        series_title="新世紀福音戰士 完全版",
        total_chapters=3,
        total_images=5,
        downloaded=2,
        skipped=1,
        output_dir=Path("downloads"),
        failed=2,
        total_bytes=2048,
        issues=(
            DownloadIssue(chapter_title="STAGE.２", kind="partial", message="1 image failed"),
            DownloadIssue(chapter_title="STAGE.３", kind="failed", message="all image downloads failed"),
        ),
    )

    report = build_download_report(summary)

    assert report.summary_text == "2 downloaded, 1 skipped, 2 failed"
    assert report.size_text == "2.0 KB"
    assert report.issue_lines == (
        "STAGE.２: 1 image failed",
        "STAGE.３: all image downloads failed",
    )
    assert report.notification_body == (
        "2 downloaded, 1 skipped, 2 failed (2.0 KB) | STAGE.２: 1 image failed | +1 more issue(s)"
    )


def test_preview_issue_lines_truncates_long_issue_list() -> None:
    summary = DownloadSummary(
        series_title="Title",
        total_chapters=6,
        total_images=0,
        downloaded=0,
        skipped=0,
        failed=6,
        output_dir=Path("downloads"),
        issues=tuple(
            DownloadIssue(chapter_title=f"Chapter {index}", kind="failed", message="all failed")
            for index in range(1, 7)
        ),
    )

    report = build_download_report(summary)

    assert report.preview_issue_lines(max_lines=3) == (
        "Chapter 1: all failed",
        "Chapter 2: all failed",
        "Chapter 3: all failed",
        "... and 3 more issue(s)",
    )
