"""Command-line interface for bilimanga-downloader."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from bilimanga_dl.core.client import BilimangaClient, DownloadSummary

if TYPE_CHECKING:
    from collections.abc import Sequence

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bilimanga-dl",
        description="Download manga chapters from bilimanga.net",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    download = sub.add_parser("download", help="Download a series, volume, or chapter URL")
    download.add_argument("url", help="bilimanga detail, volume, or reader URL")
    download.add_argument("-o", "--output", default="downloads", help="Output directory")
    download.add_argument("--limit", type=_positive_int, default=None, help="Maximum chapters to download")
    download.add_argument("--image-limit", type=_positive_int, default=None, help="Maximum images per chapter")
    download.add_argument("--headed", action="store_true", help="Show Chrome while rendering reader pages")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "download":
        return _run_async(_download(args))
    return 1


async def _download(args: argparse.Namespace) -> int:
    async with BilimangaClient(output_dir=Path(args.output), headless=not args.headed) as client:
        summary = await client.download_url(
            args.url,
            chapter_limit=args.limit,
            image_limit=args.image_limit,
        )
    _print_summary(summary)
    return 0


def _print_summary(summary: DownloadSummary) -> None:
    console.print(f"[bold green]{summary.series_title}[/bold green]")
    console.print(
        f"Downloaded {summary.downloaded} image(s), skipped {summary.skipped}, "
        f"chapters {summary.total_chapters}, output: {summary.output_dir}"
    )


def _run_async(coro: object) -> int:
    return asyncio.run(coro)  # type: ignore[arg-type]


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return value
