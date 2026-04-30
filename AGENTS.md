# Guidelines for AI Agents

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

- Whenever code is moved and changed, or a file is renamed and changed,
  do the move or the rename in one commit and make the changes in another
  commit, so that the changes are clear.

- When creating PRs, always create them as drafts with the "DON'T REVIEW
  YET" label, and always use the GitHub PR template.

- When adding PR descriptions, avoid restating the code diff. Focus on
  useful context for the reviewer.

## Testing

- **Coverage**: Changes must be covered by appropriate tests. Tests need
  to cover edge cases and failure scenarios.

- **pytest conventions**: Use pytest features like Pythonic `assert`
  statements and parametrized tests for repetitive test cases.

- **Class-based vs function-based tests**: Both styles are fine. Pick
  whichever is more readable and maintainable for the situation —
  there's no project-wide preference. Class-based tests (e.g.
  `TestCase`, `SimpleTestCase`) suit shared expensive setup and
  related test groupings; function-based tests suit standalone cases
  and pair well with parametrization and explicit fixtures.

- **Explicit fixtures**: Use [pytest-unmagic](https://github.com/dimagi/pytest-unmagic/)
  for explicit test fixtures.

- **Test doctests**: Doctests should be tested:
  ```python
  def test_doctests():
      results = doctest.testmod(some_module)
      assert results.failed == 0
  ```

- **Tests should be simple**: Tests that require a lot of patching or
  mocking are often an indicator that the code they cover needs to be
  simplified.

- **Run tests before completing**: Run the tests that cover the changes
  before considering any changes complete.

## Security

- **Implement access controls**: Ensure that permissions and access
  controls are properly implemented.

- **Prefer safe actions**: Where a destructive action, like deleting an
  instance of an important class, could have strong negative
  consequences, rather choose a less permanent action, like disabling
  the instance instead.

## Performance

- **Database queries**: For database operations, queries should be
  optimized. In rare instances this could require testing the
  performance of the query in an environment similar to production. If
  you're writing code and believe this would be beneficial, **alert the
  developer**.

- **Front-end**: For front-end code, be mindful of rendering or loading
  concerns.

## Documentation

- **Docstrings for modules and classes**: Use docstrings to give the
  purpose of a module or class. Avoid docstrings on methods or functions
  where their purpose is clear from the name.

- **Use reStructuredText format**: Follow reStructuredText conventions
  in docstrings.

- **Keep documentation in sync**: Update comments and docstrings when
  code changes are made. Keep module README files up to date.

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
