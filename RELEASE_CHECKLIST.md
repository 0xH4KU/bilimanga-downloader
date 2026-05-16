# Release Checklist

Use this checklist for every released slice.

1. Update the version in `pyproject.toml`, `src/bilimanga_dl/__init__.py`, and the README badge together.
2. Update docs affected by the release: `README.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md`, `CONTRIBUTING.md`, `MIGRATION.md`, and `todo.md`.
3. Run the local gate:

```bash
.venv/bin/ruff check .
.venv/bin/mypy src/bilimanga_dl --no-error-summary
.venv/bin/python scripts/check_docs_consistency.py
.venv/bin/pytest --cov=bilimanga_dl --cov-report=term-missing --cov-report=xml --cov-fail-under=70 -q
```

4. Run a manual smoke test that does not become a CI dependency:

```bash
bilimanga-dl doctor
bilimanga-dl download 'https://www.bilimanga.net/read/285/24327.html' --output downloads-smoke --image-limit 2 --format cbz --no-optimize
```

5. Confirm `git status --short` is clean.
6. Tag the release only after the checklist passes.
7. Push the branch and tag.
