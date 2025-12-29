# Guidelines for AI Agents

## Tech Stack

- Backend: Python, Django
- Python dependency management: uv
- Testing: pytest
- Linting & formatting: Ruff, Flake8, isort, YAPF
- Frontend: JavaScript, HTMX, Alpine.js, Knockout.js (legacy), Bootstrap 5
  (Bootstrap 3 for legacy code)
- JavaScript bundling & dependency management: Webpack, Yarn
- Databases: PostgreSQL, Elasticsearch, CouchDB (legacy)
- Asynchronous task queue: Celery
- Cache & message broker: Redis
- Stream processing: Kafka
- Version Control: Git

## Commands

- Testing: Use the `--reusedb=1` parameter to improve speed by avoiding
  resetting the test database: `pytest --reusedb=1 path/to/test.py`
- Python linting: `ruff check path/to/file.py`
- JavaScript linting: `npx eslint path/to/file.js`
- Sort imports: `ruff check --select I --fix path/to/file.py`
- Format: `ruff format path/to/file.py`

## Code Standards

### Code Clarity

- Comments: Don't use comments to indicate _what_ the code does; make
  sure that that is obvious from the code itself. Use comments to
  explain _why_ the code does what it does, and only when it might not
  be clear.

- Docstrings: Use docstrings to give the purpose of a module or class.
  Avoid docstrings on methods or functions where their purpose is clear
  from the name. Use reStructuredText format in docstrings.

- Single responsibility: Break up longer functions and methods where
  appropriate.

- Don't repeat yourself (DRY): If you suspect that similar code might have been
  needed before, search the codebase for it before implementing it. If you find
  functionality similar to what you are looking for, you may need to move it to
  keep architectural layers or Django app dependencies structured well.

- Keep docs in sync: Ensure that comments and docstrings are updated
  when code changes are made. Keep `README.md` files, and documentation
  under `docs/` directories, up-to-date with the behavior of the code.

### Testing

- Use pytest features and pytest conventions, like Pythonic `assert`
  statements, and parametrized tests for repetitive test cases.
- Use [pytest-unmagic][https://github.com/dimagi/pytest-unmagic/] for
  explicit test fixtures.
- Tests should be easy to read.
- Code changes must be covered by appropriate tests.
- Tests need to cover edge cases and failure scenarios.
- Doctests should be tested. e.g.
  ```python
  def test_doctests():
      results = doctest.testmod(some_module)
      assert results.failed == 0
  ```
- Run the tests that cover code changes before considering changes
  complete.

### Database Performance

- Database queries should be optimized. In rare instances this could
  require the Developer to test the performance of the query in an
  environment similar to production. Notify the Developer when this
  would be beneficial.

### JavaScript Guide

- The JavaScript Guide is documented under the `docs/js-guide/` directory.
