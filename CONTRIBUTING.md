# Contributing

## Scope

This project is being grown from a focused `bilimanga.net` parser into a fuller downloader using `comix-downloader` as the reference architecture. Changes should stay small, tested, and easy to review.

Avoid documenting or implementing comix.to-specific behavior here unless it has been adapted to a real bilimanga need.

## Development Environment

```bash
git clone https://github.com/0xH4KU/bilimanga-downloader.git
cd bilimanga-downloader
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

Runtime expectations:

- Python 3.11+
- Network access to `bilimanga.net`
- A desktop Chrome/Chromium install when Playwright reader fallback is needed

## Local Quality Gate

Run the same checks locally before opening a PR or making a release commit:

```bash
.venv/bin/ruff check .
.venv/bin/mypy src/bilimanga_dl --no-error-summary
.venv/bin/python scripts/check_docs_consistency.py
.venv/bin/pytest --cov=bilimanga_dl --cov-report=term-missing --cov-report=xml --cov-fail-under=70 -q
```

The enforced coverage floor is `70%`.

## Regression Test Policy

Any behavior change should include a focused test that proves the intended outcome.

Required cases:

- Parser changes must cover the affected URL shape or DOM extraction rule.
- Downloader changes must cover complete, skipped, partial, failed, and resume boundaries as applicable.
- Browser fallback changes must cover HTTP-empty reader pages and image-fetch fallback paths without requiring the real website in CI.
- CLI changes must cover parser arguments and the flow branch being introduced.
- Documentation-only changes do not need tests, but must keep docs consistency green.

## Pull Request Rules

Each PR should:

- explain the user-visible or maintenance problem being solved
- describe the chosen boundary of the change
- list validation commands that were run
- update `todo.md` only for acceptance criteria actually met

Keep unrelated refactors out of feature PRs. If a framework extraction is required, make it a separate wave with its own tests.

## Release Slice Rules

For each releasable slice:

- update `pyproject.toml`, `src/bilimanga_dl/__init__.py`, and the README version badge together
- run `scripts/check_docs_consistency.py`
- run the full quality gate
- tag as `vX.Y.Z` only after the release checklist has passed
