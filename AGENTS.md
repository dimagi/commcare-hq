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

### Debugging

```bash
# Fetch PR test failures
scripts/pr-failures.sh <pr_number>
```


## Important Notes

- Refer to `CODE_STANDARDS.md` for coding conventions and best practices
- Refer to the `docs/js-guide/` directory for the JavaScript Guide
