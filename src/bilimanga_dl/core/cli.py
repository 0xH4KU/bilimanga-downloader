"""Command-line interface for bilimanga-downloader."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.table import Table

from bilimanga_dl.core.cleanup import apply_cleanup_plan, build_cleanup_plan, list_downloaded_series
from bilimanga_dl.core.client import BilimangaClient, DownloadSummary
from bilimanga_dl.core.converters import convert, to_collection_cbz
from bilimanga_dl.core.errors import ConversionError
from bilimanga_dl.core.history import HistoryRepository
from bilimanga_dl.core.reporting import DownloadIssue, build_download_report, format_bytes, format_download_counts
from bilimanga_dl.core.runtime import detect_chrome_path
from bilimanga_dl.core.selection import apply_chapter_filters as _apply_chapter_filters
from bilimanga_dl.core.selection import parse_chapter_selection as _parse_chapter_selection
from bilimanga_dl.core.settings import SettingsRepository

if TYPE_CHECKING:
    from collections.abc import Sequence

    from bilimanga_dl.core.models import SeriesInfo

console = Console()
_COMMANDS = {"download", "info", "list", "clean", "history", "doctor", "settings"}


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="bilimanga-dl",
        description="Download manga chapters from bilimanga.net",
    )
    parser.add_argument("--quiet", action="store_true", help="Minimal output")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    sub = parser.add_subparsers(dest="command", required=False)

    download = sub.add_parser("download", help="Download a series, volume, or chapter URL")
    download.add_argument("url", help="bilimanga detail, volume, or reader URL")
    download.add_argument("-c", "--chapters", default="all", help="Chapter selection: all, 1, 1-5, 1,3,5")
    download.add_argument(
        "--filter",
        dest="filters",
        action="append",
        default=[],
        help="Chapter filter: +keyword/-keyword",
    )
    download.add_argument("-f", "--format", choices=["pdf", "cbz", "both"], default=None)
    download.add_argument("--package", choices=["chapter", "volume", "both"], default="chapter")
    download.add_argument("-o", "--output", default=None, help="Output directory")
    download.add_argument("--no-optimize", action="store_true", help="Skip WebP optimization before conversion")
    download.add_argument(
        "--chapter-concurrency",
        type=_positive_int,
        default=None,
        help="Number of chapters to download in parallel",
    )
    download.add_argument("--quiet", action="store_true", help=argparse.SUPPRESS)
    download.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    download.add_argument("--limit", type=_positive_int, default=None, help=argparse.SUPPRESS)
    download.add_argument("--image-limit", type=_positive_int, default=None, help=argparse.SUPPRESS)
    download.add_argument("--headed", action="store_true", help="Show Chrome while rendering reader pages")

    info = sub.add_parser("info", help="Show series metadata")
    info.add_argument("url", help="bilimanga URL or manga id")

    sub.add_parser("list", help="List downloaded series")

    clean = sub.add_parser("clean", help="Remove raw image dirs after conversion")
    clean.add_argument("--force", action="store_true", help="Skip confirmation")

    history = sub.add_parser("history", help="Show or clear download history")
    history.add_argument("action", nargs="?", choices=["clear"], default=None)

    sub.add_parser("doctor", help="Run environment diagnostics")
    sub.add_parser("settings", help="Show current settings")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    actual_argv = list(sys.argv[1:] if argv is None else argv)
    if _is_bare_url_download(actual_argv):
        settings = SettingsRepository().load()
        args = argparse.Namespace(
            command="download",
            url=actual_argv[0],
            output=settings.output_dir,
            limit=None,
            image_limit=None,
            headed=False,
            format=settings.default_format,
            package="chapter",
            chapter_concurrency=None,
            no_optimize=not settings.optimize_images,
            quiet=False,
            debug=False,
            chapters="all",
            filters=[],
        )
    else:
        args = build_parser().parse_args(actual_argv)

    if args.command == "download":
        return _run_async(_download(args))
    if args.command == "info":
        return _run_async(_info(args.url))
    if args.command == "list":
        return _list_downloads()
    if args.command == "clean":
        return _clean(force=args.force)
    if args.command == "history":
        return _history(action=args.action)
    if args.command == "doctor":
        return _doctor()
    if args.command == "settings":
        return _settings()
    build_parser().print_help()
    return 0


parse_chapter_selection = _parse_chapter_selection
apply_chapter_filters = _apply_chapter_filters


async def _download(args: argparse.Namespace) -> int:
    settings = SettingsRepository().load()
    tuning = SettingsRepository.resolve_download_tuning(settings)
    output = Path(args.output or settings.output_dir)
    async with BilimangaClient(output_dir=output, headless=not args.headed) as client:
        summary = await client.download_url(
            args.url,
            chapter_limit=args.limit,
            image_limit=args.image_limit,
            chapters_selection=args.chapters,
            chapter_filters=args.filters,
            chapter_concurrency=args.chapter_concurrency or tuning.concurrent_chapters,
        )

    conversion_issues = _convert_downloaded_chapters(
        summary,
        fmt=args.format or settings.default_format,
        package_mode=args.package,
        optimize=not args.no_optimize,
    )
    if conversion_issues:
        summary = _summary_with_issues(summary, conversion_issues)
    _print_summary(summary)
    return 1 if conversion_issues else 0


async def _info(url: str) -> int:
    info = await _load_series_info(url)
    _print_series_info(info)
    return 0


async def _load_series_info(url_or_id: str) -> SeriesInfo:
    """Load framework series metadata using the active client engine."""
    from bilimanga_dl.sites import get_for_url
    from bilimanga_dl.sites.bilimanga import BilimangaAdapter

    adapter = get_for_url(url_or_id) or BilimangaAdapter()
    identifier = adapter.parse_identifier(url_or_id) or url_or_id
    async with BilimangaClient() as client:
        return await adapter.get_series(client, identifier)


def _print_series_info(info: Any) -> None:
    chapters = getattr(info, "chapters", [])
    console.print(f"[bold green]{getattr(info, 'title', '')}[/bold green]")
    console.print(f"Chapters: {len(chapters)}")
    url = getattr(info, "url", "")
    if url:
        console.print(f"URL: {url}")


def _list_downloads() -> int:
    settings = SettingsRepository().load()
    output_dir = Path(settings.output_dir)
    entries = list_downloaded_series(output_dir)
    if not entries:
        console.print("[dim]No downloaded series found.[/dim]")
        return 0

    table = Table(title="Downloaded Series")
    table.add_column("Series")
    table.add_column("Chapters", justify="right")
    table.add_column("Size", justify="right")
    for item in entries:
        table.add_row(item.name, str(item.completed_chapters), format_bytes(item.total_size_bytes))
    console.print(table)
    return 0


def _clean(*, force: bool = False) -> int:
    settings = SettingsRepository().load()
    plan = build_cleanup_plan(Path(settings.output_dir))
    if not plan.candidates:
        console.print("[dim]Nothing to clean.[/dim]")
        return 0
    if not force:
        console.print("[yellow]Use --force to remove raw image directories.[/yellow]")
        return 1
    result = apply_cleanup_plan(plan)
    console.print(f"[green]Removed {result.removed_count} directorie(s).[/green]")
    for path, message in result.failed:
        console.print(f"[red]{path}: {message}[/red]")
    return 0 if not result.failed else 1


def _history(*, action: str | None = None) -> int:
    repository = HistoryRepository()
    if action == "clear":
        repository.clear()
        console.print("[green]History cleared.[/green]")
        return 0

    entries = repository.list_entries()
    if not entries:
        console.print("[dim]No download history.[/dim]")
        return 0

    table = Table(title="Download History")
    table.add_column("Date")
    table.add_column("Title")
    table.add_column("Chapters", justify="right")
    table.add_column("Format")
    table.add_column("Status")
    for entry in entries:
        status = entry.summary_text or format_download_counts(
            completed=entry.completed,
            skipped=entry.skipped,
            partial=entry.partial,
            failed=entry.failed,
        )
        table.add_row(entry.timestamp[:10], entry.title, str(entry.chapters_count), entry.format, status)
    console.print(table)
    return 0


def _settings() -> int:
    settings = SettingsRepository().load()
    tuning = SettingsRepository.resolve_download_tuning(settings)
    console.print("[bold]Settings[/bold]")
    console.print(f"Output: {settings.output_dir}", soft_wrap=True)
    console.print(f"Format: {settings.default_format}")
    console.print(f"Profile: {settings.concurrency_profile}")
    console.print(f"Chapters: {tuning.concurrent_chapters}")
    console.print(f"Images: {tuning.concurrent_images}")
    console.print(f"Optimize: {settings.optimize_images}")
    return 0


def _doctor() -> int:
    settings = SettingsRepository().load()
    all_ok = True
    console.print("[bold]bilimanga-dl doctor[/bold]")
    console.print(f"Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    for module_name, label in [("httpx", "httpx"), ("playwright", "playwright"), ("PIL", "Pillow"), ("pypdf", "pypdf")]:
        try:
            __import__(module_name)
            console.print(f"{label}: ok")
        except ImportError:
            console.print(f"{label}: missing")
            all_ok = False
    chrome_path = Path(detect_chrome_path())
    if chrome_path.exists():
        console.print(f"Chrome: {chrome_path}")
    else:
        console.print(f"Chrome: not found ({chrome_path})")
        all_ok = False
    output_dir = Path(settings.output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"Output: {output_dir}")
    except OSError:
        console.print(f"Output: cannot create {output_dir}")
        all_ok = False
    console.print("bilimanga URL probe: configured")
    return 0 if all_ok else 1


def _print_summary(summary: DownloadSummary) -> None:
    report = build_download_report(summary)
    console.print(f"[bold green]{summary.series_title}[/bold green]")
    console.print(
        f"Downloaded {summary.downloaded} image(s), skipped {summary.skipped}, "
        f"failed {summary.failed}, chapters {summary.total_chapters}, output: {summary.output_dir}"
    )
    console.print(report.summary_text)
    for line in report.preview_issue_lines():
        console.print(line)


def _convert_downloaded_chapters(
    summary: DownloadSummary,
    *,
    fmt: str,
    package_mode: str = "chapter",
    optimize: bool,
) -> tuple[DownloadIssue, ...]:
    if fmt not in {"pdf", "cbz", "both"}:
        return ()
    issues: list[DownloadIssue] = []
    if package_mode in {"chapter", "both"}:
        for chapter_dir in _iter_complete_chapter_dirs(summary.output_dir):
            converted_pdf = chapter_dir.parent / f"{chapter_dir.name}.pdf"
            converted_cbz = chapter_dir.parent / f"{chapter_dir.name}.cbz"
            if fmt == "pdf" and converted_pdf.exists():
                continue
            if fmt == "cbz" and converted_cbz.exists():
                continue
            if fmt == "both" and converted_pdf.exists() and converted_cbz.exists():
                continue
            try:
                convert(chapter_dir, fmt, optimize=optimize)
            except ConversionError as exc:
                issues.append(
                    DownloadIssue(
                        chapter_title=chapter_dir.name,
                        kind="conversion_failed",
                        message=f"conversion failed: {exc}",
                    )
                )
    if package_mode in {"volume", "both"}:
        if fmt == "pdf":
            issues.append(
                DownloadIssue(
                    chapter_title=summary.series_title,
                    kind="conversion_failed",
                    message="Volume packaging only supports CBZ; use --format cbz or --format both.",
                )
            )
        else:
            issues.extend(_convert_downloaded_volumes(summary))
    return tuple(issues)


def _convert_downloaded_volumes(summary: DownloadSummary) -> tuple[DownloadIssue, ...]:
    issues: list[DownloadIssue] = []
    by_volume: dict[str, list[tuple[str, Path]]] = {}
    for index, chapter in enumerate(summary.chapters, start=1):
        if not (chapter.chapter_dir / ".complete").exists():
            continue
        by_volume.setdefault(chapter.volume_title, []).append((f"{index:03d} {chapter.title}", chapter.chapter_dir))
    series_dir = summary.output_dir / _safe_path_segment(summary.series_title)
    for volume_title, chapters in by_volume.items():
        try:
            to_collection_cbz(chapters, series_dir / f"{_safe_path_segment(volume_title)}.cbz")
        except ConversionError as exc:
            issues.append(
                DownloadIssue(
                    chapter_title=volume_title,
                    kind="conversion_failed",
                    message=f"conversion failed: {exc}",
                )
            )
    return tuple(issues)


def _safe_path_segment(value: str) -> str:
    unsafe_chars = '\\/*?"<>|:'
    cleaned = value.translate(str.maketrans(unsafe_chars, " " * len(unsafe_chars)))
    return " ".join(cleaned.replace("..", "").split()).strip(" .") or "download"


def _summary_with_issues(summary: DownloadSummary, issues: tuple[DownloadIssue, ...]) -> DownloadSummary:
    return DownloadSummary(
        series_title=summary.series_title,
        total_chapters=summary.total_chapters,
        total_images=summary.total_images,
        downloaded=summary.downloaded,
        skipped=summary.skipped,
        output_dir=summary.output_dir,
        partial=summary.partial,
        failed=summary.failed + len(issues),
        total_bytes=summary.total_bytes,
        issues=(*summary.issues, *issues),
        chapters=summary.chapters,
    )


def _iter_complete_chapter_dirs(output_dir: Path) -> list[Path]:
    if not output_dir.exists():
        return []
    return sorted(
        chapter_dir
        for series_dir in output_dir.iterdir()
        if series_dir.is_dir()
        for chapter_dir in series_dir.iterdir()
        if chapter_dir.is_dir() and (chapter_dir / ".complete").exists()
    )


def _is_bare_url_download(argv: list[str]) -> bool:
    return len(argv) == 1 and argv[0] not in _COMMANDS and not argv[0].startswith("-")


def _run_async(coro: object) -> int:
    return asyncio.run(coro)  # type: ignore[arg-type]


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return value
