# Development

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

The project uses `src/` layout and exposes the console script `bilimanga-dl`.

## Local Checks

```bash
.venv/bin/ruff check .
.venv/bin/mypy src/bilimanga_dl --no-error-summary
.venv/bin/python scripts/check_docs_consistency.py
.venv/bin/pytest --cov=bilimanga_dl --cov-report=term-missing --cov-report=xml --cov-fail-under=70 -q
```

Run the full gate before committing a wave.

## Focused Test Commands

Parser:

```bash
.venv/bin/pytest tests/test_bilimanga_parser.py tests/test_url_handling.py -q
```

Downloader:

```bash
.venv/bin/pytest tests/test_downloader.py -q
```

Client / fallback orchestration:

```bash
.venv/bin/pytest tests/test_client.py tests/test_reader.py -q
```

CLI:

```bash
.venv/bin/pytest tests/test_cli.py -q
```

## Real-Site Smoke Test

CI should not depend on live `bilimanga.net` responses. Before release, run a manual smoke test with a small image limit:

```bash
bilimanga-dl download "https://www.bilimanga.net/read/285/24327.html" --output downloads-smoke --image-limit 2
```

Expected result:

- command exits `0`
- one chapter directory is created under `downloads-smoke/`
- two image files are present
- `.complete` exists only when both image files were fetched

If the site returns a desktop-block reader page, re-run with `--headed` so Playwright can render the mobile reader fallback.
