# Code Standards for CommCare HQ

This document outlines coding standards and best practices for the
CommCare HQ codebase. These guidelines apply when reviewing code,
writing code, or making changes to the project.

## General Principles

- **Clarity, maintainability, and performance** are important.
  Prioritize clarity and maintainability higher than performance.
  Situations where performance must come at the cost of clarity or
  maintainability should be documented using comments.

- Consider both immediate needs and long-term implications.

## Structure

- **Single responsibility**: Keep functions and methods focused on a
  single responsibility. Break up longer functions where appropriate.

- **Don't repeat yourself (DRY)**: If you suspect that similar code
  might have been needed before, search the codebase for it before
  implementing it. If you find functionality similar to what you are
  looking for, you may need to move it to keep architectural layers or
  Django app dependencies structured well.

## Documentation

- **Comments explain "why" not "what"**: The "what" should be clear from
  the code itself. Use comments to explain reasoning that might not be
  immediately clear.

- **Docstrings for modules and classes**: Use docstrings to give the
  purpose of a module or class. Avoid docstrings on methods or functions
  where their purpose is clear from the name.

- **Use reStructuredText format**: Follow reStructuredText conventions
  in docstrings.

- **Keep documentation in sync**: Update comments and docstrings when
  code changes are made. Keep module README files up to date.

## Testing

- **Coverage**: Changes must be covered by appropriate tests. Tests need
  to cover edge cases and failure scenarios.

- **pytest conventions**: Use pytest features like Pythonic `assert`
  statements and parametrized tests for repetitive test cases.

- **Explicit fixtures**: Use [pytest-unmagic](https://github.com/dimagi/pytest-unmagic/)
  for explicit test fixtures.

- **Test doctests**: Doctests should be tested:
  ```python
  def test_doctests():
      results = doctest.testmod(some_module)
      assert results.failed == 0
  ```

- **Run tests before completing**: Run the tests that cover the changes
  before considering any changes complete.

## Performance

- **Database queries**: For database operations, queries should be
  optimized. In rare instances this could require testing the
  performance of the query in an environment similar to production. If
  you're writing code and believe this would be beneficial, notify the
  developer.

- **Front-end**: For front-end code, be mindful of rendering or loading
  concerns.

## Security

- **Prevent vulnerabilities**: Be careful not to introduce security
  vulnerabilities such as command injection, XSS, SQL injection, and
  other OWASP top 10 vulnerabilities. If you notice insecure code,
  immediately fix it.

- **Validate input**: Ensure that user input is properly validated and
  sanitized.

- **Implement access controls**: Ensure that permissions and access
  controls are properly implemented.

- **Prefer safe actions**: Where a destructive action, like deleting an
  instance of an important class, could have strong negative
  consequences, rather choose a less permanent action, like disabling
  the instance instead.

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

## Version Control

- **Logical commits**: When changes are ready to be committed, break
  them into logical steps to make reviewing easier. Each step should be
  staged with a suggested commit message that summarizes the step.
