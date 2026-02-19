# Guidelines for AI Agents

This document provides technical information about the CommCare HQ codebase
for AI coding assistants. For coding standards and best practices, see
`CODE_STANDARDS.md`.

## Tech Stack

- Backend: Python, Django
- Python dependency management: uv
- Testing: pytest
- Linting: Flake8
- Formatting & import sorting: Ruff
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

### Testing

```bash
# Run tests with database reuse for faster execution
pytest --reusedb=1 path/to/test.py
```

Use the `--reusedb=1` parameter when running tests to avoid resetting
the test database unnecessarily

### Linting

```bash
# Python linting
flake8 path/to/file.py

# JavaScript linting
npx eslint path/to/file.js
```

### Formatting

```bash
# Sort Python imports
ruff check --select I --fix path/to/file.py

# Format Python code
ruff format path/to/file.py

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

### Debugging

```bash
# Fetch PR test failures
scripts/pr-failures.sh <pr_number>
```


## Gotchas

- **CouchDB is legacy** — prefer PostgreSQL/SQL for new data models
- **Knockout.js is legacy** — prefer HTMX or Alpine.js for new frontend code
- **Bootstrap 3 is legacy** — prefer Bootstrap 5; both coexist in the codebase

## Important Notes

- Refer to `CODE_STANDARDS.md` for coding conventions and best practices
- Refer to the `docs/js-guide/` directory for the JavaScript Guide
