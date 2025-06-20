# Guidelines for CommCare HQ

This document outlines recommended practices for working with the CommCare HQ
codebase. These guidelines apply in the following circumstances:

- Reviewing code or suggesting changes
- Writing code and making changes
- Assisting with version control

## General Principles

- Focus on clarity, maintainability, and performance
- Consider both immediate needs and long-term implications

## Communication

### For the AI Assistant

- The AI Assistant should maintain professional, focused communication.
- The AI Assistant should ask clarifying questions whenever details are unclear,
  or choices are not obvious.
- When appropriate, the AI Assistant should make recommendations on how the
  Developer can improve their prompt to get a more effective response.

### For the Developer

- The Developer should provide feedback to the AI Assistant to improve future
  responses.
- The Developer should update this document to assist the AI Assistant across
  sessions, and to improve the interactions of other Developers.

## Tech Stack

- Backend: Python, Django
- Frontend: JavaScript, HTMX, Alpine.js, Knockout.js (legacy)
- Databases: PostgreSQL, Elasticsearch, CouchDB (legacy)
- Asynchronous task queue: Celery
- Cache & message broker: Redis
- Stream processing: Kafka
- Version Control: Git

## Writing and Reviewing Code

### Code Clarity

- Is the code readable and well-structured?
- Does it follow codebase conventions?
- Are there any potential bugs or edge cases?
- Keep functions and methods focused on a single responsibility. Break up
  longer functions where appropriate.

### Performance

- Are there any potential performance bottlenecks?
- For database operations, are queries optimized?
- For front-end code, are there rendering or loading concerns?

### Maintainability

- Have comments or docstrings that are affected by the change been updated?
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

- Are there any security vulnerabilities?
- Is user input properly validated and sanitized?
- Are permissions and access controls properly implemented?

### Testing

- Are there appropriate tests for the changes?
- Do the tests cover edge cases and failure scenarios?
- Are the tests clear and maintainable?
- Are doctests tested?
- Run the test suite before submitting changes
- Use pytest features and pytest conventions, like Pythonic `assert`
  statements, and parametrized tests for repetitive parameter values.
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
