# Guidelines for CommCare HQ

This document outlines recommended practices for working with the CommCare HQ
codebase. These guidelines apply in the following circumstances:

- Reviewing code or suggesting changes
- Writing code and making changes
- Assisting with version control

## General Principles

- Clarity, maintainability and performance are important. Prioritize clarity
  and maintainability higher than performance. Situations where performance
  must come at the cost of clarity or maintainability should be documented
  using comments.
- Consider both immediate needs and long-term implications.

## Communication

- The AI Assistant should ask clarifying questions whenever details are unclear,
  or choices are not obvious.
- When appropriate, the AI Assistant should make recommendations on how the
  Developer can improve their prompt to get a more effective response.

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

## Writing and Reviewing Code

### Code Clarity

- Code should be readable and well-structured.
- Code should follow the conventions used in the rest of the module.
- When writing or reviewing code, consider any potential bugs or edge cases.
- Keep functions and methods focused on a single responsibility. Break up
  longer functions where appropriate.
- Don't repeat yourself (DRY). If you suspect that similar code might have been
  needed before, search the codebase for if before implementing it. If you find
  functionality similar to what you are looking for, you may need to move it to
  keep architectural layers or Django app dependencies structured well.

### Performance

- Consider potential performance bottlenecks.
- For database operations, queries should be optimized. In rare instances this
  could require the Developer to test the performance of the query in an
  environment similar to production. If the AI Assistant is writing code, then
  notify the Developer when this would be beneficial.
- For front-end code, be mindful of rendering or loading concerns.

### Maintainability

- Update comments and docstrings affected by incoming changes.
- Document complex logic, algorithms, and business rules.
- Not all functions, classes and methods ought to have docstrings. Where
  functionality is not obvious just from the name, a docstring should be
  present and helpful. For usage examples, include one, or at most two, short
  doctests where appropriate.
- Comments should explain "why" rather than "what": As much as possible,
  "what" should be clear from the code.
- Keep module README files and project documentation under `docs/`
  up-to-date.

### Security

- Always consider security vulnerabilities.
- Ensure that user input is properly validated and sanitized.
- Ensure that permissions and access controls are properly implemented.
- Where a destructive action, like deleting an instance of an important class,
  could have strong negative consequences, rather choose a less permanent
  action, like disabling the instance instead.

### Testing

- Changes must be covered by appropriate tests.
- Tests need to cover edge cases and failure scenarios.
- Tests should be clear and maintainable.
- Doctests should be tested.
- Run the tests that cover the changes before considering any changes complete.
- Use pytest features and pytest conventions, like Pythonic `assert`
  statements, and parametrized tests for repetitive test cases.
- Use [pytest-unmagic][1] for explicit test fixtures.

[1]: https://github.com/dimagi/pytest-unmagic/blob/main/README.md#usage

## Codebase Conventions & Coding Guides

- The JavaScript Guide is documented under the `docs/js-guide/` directory.

- Python is _optionally_ formatted using **yapf**:

  ```shell
  source .venv/bin/activate
  yapf -i example/path/filename.py
  ```

  AI Tool and Developer discretion is required:

  - A line length of 115 is enforced. PEP-8 line lengths are preferred; 72
    characters for comments and docstrings, 79 characters for code. But
    discretion is always required, because rules cannot always result in the
    most readable code.

  - Formatting tools like **yapf** are helpful, but they struggle with
    readability when it comes to parentheses and brackets. For example,

    **yapf** (less readable):
    ```python
    repeat_records = (
        self.get_queryset().filter(is_paused=False
                                  ).filter(next_attempt_at__lte=timezone.now()
                                          ).filter(repeat_records__state__in=RECORD_QUEUED_STATES)
    )
    ```

    **Developer** (more readable):
    ```python
    repeat_records = (
        self.get_queryset()
        .filter(is_paused=False)
        .filter(next_attempt_at__lte=timezone.now())
        .filter(repeat_records__state__in=RECORD_QUEUED_STATES)
    )
    ```

    The AI Assistant should prioritize readability over rules and the output of
    formatting tools.

## Version Control

- When changes are ready to be committed, the changes should be broken into
  logical steps to make reviewing easier. Each step should be staged with a
  suggested commit message that summarizes the step.
- The AI Assistant should leave it to the developer to commit the staged
  changes, and to sign the commit if applicable.
