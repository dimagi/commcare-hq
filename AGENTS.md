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

**Activate the virtualenv** before running any commands to ensure tools
like `ruff`, `pytest`, and `manage.py` are available:

```bash
source .venv/bin/activate
```

### Dependencies

```bash
# Install/sync Python dependencies
uv sync
```

### Running the app

```bash
./manage.py runserver
```

### Testing

```bash
# Run tests with database reuse for faster execution
pytest --reusedb=1 path/to/test.py

# If tests fail due to schema changes, migrate the test DB:
pytest --reusedb=migrate path/to/test.py
```

Use `pytest-unmagic` for explicit test fixtures (see `CODE_STANDARDS.md`).
Notable markers: `es_test` (Elasticsearch), `sharded` (shard DBs), `slow`.

### Linting

```bash
# Python linting
ruff check path/to/file.py

# JavaScript linting
npx eslint path/to/file.js
```

### Formatting

```bash
# Sort Python imports
ruff check --select I --fix path/to/file.py

# Format Python code
ruff format path/to/file.py

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

### Debugging

```bash
# Fetch PR test failures
scripts/pr-failures.sh [pr_number]  # uses current branch if omitted
```

## Gotchas

- **migrations.lock** — If you wrote a migration instead of generating one,
  run `./manage.py makemigrations --lock-update` to update the lock file.
- **New domain-scoped models** — Any new model with a `domain` field (or
  reachable via FK to a domain) must be registered in two places or CI will
  fail:
  - `corehq/apps/dump_reload/sql/dump.py` — add a
    `FilteredModelIteratorBuilder` entry so the model is included in domain
    data exports.
  - `corehq/apps/domain/deletion.py` — add a `ModelDeletion` entry so the
    model is cleaned up when a domain is deleted.
  Use `SimpleFilter('domain')` for direct domain fields, or
  `SimpleFilter('parent__domain')` for FK traversal.
- **CouchDB is legacy** — Use PostgreSQL for new data models
- **Knockout.js is legacy** — Prefer HTMX or Alpine.js for new frontend code
- **Bootstrap 3 is legacy** — Prefer Bootstrap 5; both coexist in the codebase

## Version Control

- Always commit on a branch, never directly on master.
- When creating a new branch, each author has a prefix they use. Use the
  prefix the author has used most on local git branches, or else their
  initials (from `git config user.name`).
- Commit work in logical chunks rather than one large commit. Group related
  changes together (e.g. a new module with its tests, a migration with its
  model changes) so that each commit is self-contained and reviewable.
- When creating PRs, always create them as drafts with the "DON'T REVIEW
  YET" label, and always use the GitHub PR template.
- When adding PR descriptions, avoid restating the code diff. Focus on
  useful context for the reviewer.
