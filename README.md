# bilimanga-downloader

[![Version](https://img.shields.io/badge/version-0.1.0-blue?style=flat-square)](https://github.com/0xH4KU/bilimanga-downloader)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

Focused `bilimanga.net` parser and downloader, grown from the same architecture used by `comix-downloader`: site parsing lives under `sites/`, shared runtime lives under `core/`, and the CLI is a thin orchestration layer.

## Features

- Supports bilimanga detail, volume, and reader URLs.
- Uses mobile-shaped HTTP first, with Playwright rendering fallback when reader pages or images are blocked.
- Resumable image downloads with retries, atomic writes, corrupt-file recovery, partial state files, and path traversal protection.
- Outputs raw images, PDF, CBZ, or both. Partial chapters are never converted.
- Includes settings, download history, summary reports, cleanup helpers, and best-effort desktop notifications.
- Provides `doctor`, `list`, `clean`, `history`, and `settings` commands for everyday maintenance.

## Install

Local development install:

```bash
python -m pip install -e '.[dev]'
python -m playwright install chromium
```

One-command install from a checkout:

```bash
./install.sh
```

Windows PowerShell:

```powershell
.\install.ps1
```

## Usage

Download a reader URL:

```bash
bilimanga-dl download 'https://www.bilimanga.net/read/285/24327.html' --output downloads
```

Bare URLs are treated as downloads:

```bash
bilimanga-dl 'https://www.bilimanga.net/read/285/24327.html'
```

Select chapters and output format:

```bash
bilimanga-dl download 'https://www.bilimanga.net/detail/285.html' --chapters 1-5 --format both
bilimanga-dl download 'https://www.bilimanga.net/detail/285.html' --chapters 1,3,5 --format cbz --no-optimize
```

Filter chapters before selection:

```bash
bilimanga-dl download 'https://www.bilimanga.net/detail/285.html' --filter '+STAGE' --filter '-番外'
```

Inspect and maintain local downloads:

```bash
bilimanga-dl info 285
bilimanga-dl list
bilimanga-dl clean --force
bilimanga-dl history
bilimanga-dl history clear
bilimanga-dl settings
bilimanga-dl doctor
```

Supported URL shapes:

- `https://www.bilimanga.net/detail/285.html`
- `https://www.bilimanga.net/detail/285/vol_24326.html`
- `https://www.bilimanga.net/read/285/24327.html`

## Settings

Settings are stored at:

```text
~/.config/bilimanga-dl/settings.json
```

The default output directory is:

```text
~/Downloads/bilimanga-dl
```

Supported concurrency profiles:

- `desktop`
- `low_resource`
- `ci`
- `custom`

## How It Works

`BilimangaHttpClient` fetches pages and images with headers accepted by the mobile reader. If a reader page returns no image tags, or an image request is blocked with a recoverable status, `PlaywrightBrowser` renders the page or loads the image response through Chromium.

The downloader writes images atomically, validates existing files by magic bytes before resuming, and writes `chapter.state.json` for partial or failed chapters. Only directories with `.complete` and no partial state file are eligible for PDF/CBZ conversion and cleanup.

## Development

```bash
.venv/bin/ruff check .
.venv/bin/mypy src/bilimanga_dl --no-error-summary
.venv/bin/python scripts/check_docs_consistency.py
.venv/bin/pytest --cov=bilimanga_dl --cov-report=term-missing --cov-report=xml --cov-fail-under=70 -q
```

Live website smoke tests are manual; CI should not depend on `bilimanga.net`.
