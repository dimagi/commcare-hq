# Guidelines for AI Agents

## Tech Stack

- Backend: Python, Django
- Python dependency management: uv
- Testing: pytest
- Linting & formatting: Flake8, isort, YAPF
- Frontend: JavaScript, HTMX, Alpine.js, Knockout.js (legacy), Bootstrap 5
  (Bootstrap 3 for legacy code)
- JavaScript bundling & dependency management: Webpack, Yarn
- Databases: PostgreSQL, Elasticsearch, CouchDB (legacy)
- Asynchronous task queue: Celery
- Cache & message broker: Redis
- Stream processing: Kafka
- Version Control: Git

## Code Clarity

- Keep functions and methods focused on a single responsibility. Break up
  longer functions where appropriate.
- Don't repeat yourself (DRY). If you suspect that similar code might have been
  needed before, search the codebase for if before implementing it. If you find
  functionality similar to what you are looking for, you may need to move it to
  keep architectural layers or Django app dependencies structured well.

### Performance

- For database operations, queries should be optimized. In rare instances this
  could require the Developer to test the performance of the query in an
  environment similar to production. If the AI Assistant is writing code, then
  notify the Developer when this would be beneficial.

### Maintainability

- Update comments and docstrings affected by incoming changes.
- Not all functions, classes and methods ought to have docstrings. Where
  functionality is not obvious just from the name, a docstring should be
  present and helpful. For usage examples, include one, or at most two, short
  doctests where appropriate.
- Comments should explain "why" rather than "what": As much as possible,
  "what" should be clear from the code.
- Keep module README files and project documentation under `docs/`
  up-to-date.

### Testing

- Changes must be covered by appropriate tests.
- Tests need to cover edge cases and failure scenarios.
- Tests should be clear and maintainable.
- Doctests should be tested.
- Run the tests that cover the changes before considering any changes complete.
- Tests should be run with the `--reusedb=1` parameter to improve speed by
  avoiding resetting the test database. e.g.
  ```shell
  $ uv run pytest --reusedb=1 path/to/test.py
  ```
- Use pytest features and pytest conventions, like Pythonic `assert`
  statements, and parametrized tests for repetitive test cases.
- Use [pytest-unmagic][1] for explicit test fixtures.

[1]: https://github.com/dimagi/pytest-unmagic/blob/main/README.md#usage

## Code Style

- The JavaScript Guide is documented under the `docs/js-guide/` directory.

- Check JavaScript linting using
  ```shell
  $ npx eslint path/to/file.js
  ```

- Check Python linting using
  ```shell
  $ uv run flake8 path/to/file.py
  ```

- Python imports are kept clean and consistent using **isort**:
  ```shell
  $ uv run isort path/to/file.py
  ```
