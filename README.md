# bilimanga-downloader

[![Version](https://img.shields.io/badge/version-0.1.0-blue?style=flat-square)](https://github.com/0xH4KU/bilimanga-downloader)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

Focused parser and downloader for `bilimanga.net`.

The project follows the same separation used in `comix-downloader`: site-specific parsing lives under `sites/`, shared models live under `core/`, and the CLI only orchestrates those pieces.

## Usage

```bash
python -m pip install -e '.[dev]'
bilimanga-dl download 'https://www.bilimanga.net/read/285/24327.html' --output downloads --image-limit 2
```

Supported URL shapes:

- `https://www.bilimanga.net/detail/285.html`
- `https://www.bilimanga.net/detail/285/vol_24326.html`
- `https://www.bilimanga.net/read/285/24327.html`

Reader pages are fetched with the site cookie needed for image HTML. If the site falls back to its desktop-block page, the downloader can render with Playwright as a backup; on macOS it prefers the installed Google Chrome at `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` when it exists.
