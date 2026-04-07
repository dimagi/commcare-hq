# Guidelines for AI Agents

This document provides technical information about the CommCare HQ codebase
for AI coding assistants. For coding standards and best practices, see
`CODE_STANDARDS.md`.

## Tech Stack

- Backend: Python, Django
- Python dependency management: uv
- Testing: pytest
- Linting, formatting, & import sorting: Ruff
- Frontend: JavaScript, HTMX, Alpine.js, Knockout.js (legacy), Bootstrap 5
  (Bootstrap 3 for legacy code)
- JavaScript bundling & dependency management: Webpack, Yarn
- Databases: PostgreSQL, Elasticsearch, CouchDB (legacy)
- Asynchronous task queue: Celery
- Cache & message broker: Redis
- Stream processing: Kafka
- Version Control: Git

## Architecture

- `corehq/apps/` — primary Django app directory; most feature work lives here
- `corehq/ex-submodules/` — internal packages added to the Python path
- `submodules/` — git submodules also on the Python path
- `localsettings.py` — local dev configuration (copy from `localsettings.example.py`)
- `testsettings.py` — Django settings module used by pytest

## Common Commands

Use command prefix `uv run` to run Python commands in the uv virtualenv.

### Sync Python dev dependencies

```bash
uv sync --compile-bytecode && uv pip install -r requirements/local.txt
```

### Testing

```bash
# Run tests with database reuse for faster execution
uv run pytest --reusedb=1 path/to/test.py

# If tests fail due to schema changes, migrate the test DB:
uv run pytest --reusedb=migrate path/to/test.py
```

Use `pytest-unmagic` for explicit test fixtures (see `CODE_STANDARDS.md`).
Notable markers: `es_test` (Elasticsearch), `sharded` (shard DBs), `slow`.

### Linting

```bash
# Python linting
uv run ruff check path/to/file.py

# JavaScript linting
npx eslint path/to/file.js
```

### Formatting

```bash
# Sort Python imports
uv run ruff check --select I --fix path/to/file.py

# Format Python code
uv run ruff format path/to/file.py

# Format HTML templates
npx prettier --write path/to/template.html

# Format Markdown files
npx prettier --write path/to/file.md
```

Automated formatting and import-sorting changes should be committed
separately from logic changes to keep diffs reviewable.

### JavaScript

```bash
# Watch and rebuild JS during development
yarn dev

# Production build
yarn build
```

Refer to the `docs/js-guide/` directory for the JavaScript Guide

### Frontend Style

Refer to the `corehq/apps/styleguide/` app (run locally at `/a/styleguide/`) for the
UI Style Guide — Bootstrap 5 conventions, button patterns, accessibility requirements,
and HTML/template guidelines for new frontend code.

### Debugging

```bash
# Fetch PR test failures
scripts/pr-failures.sh [pr_number]  # uses current branch if omitted
```
