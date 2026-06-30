# Bulk Async Form Action Core Refactor (SAAS-19975) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract a pure, structured core (`iter_form_action_results`) out of `archive_or_restore_forms`, add blob payload helpers for `BulkAsyncJob`, and re-implement `archive_or_restore_forms` as a thin shim — with no behavior change except folding wrong-domain into `not_found`.

**Architecture:** A pure generator `iter_form_action_results(domain, form_ids, action_fn)` yields one `FormActionResult` per requested id (`succeeded` / `skipped` with a `reason`). The legacy `archive_or_restore_forms` becomes a throwaway shim that builds the action callable, consumes the core, and re-adds today's i18n message shape + `DownloadBase` progress. Standalone blob helpers read/write the `requested_ids` / `skipped_ids` JSON payloads for the eventual cutover.

**Tech Stack:** Python, Django, pytest, CommCare HQ blob DB (`CODES.bulk_async_job`), `dataclasses`.

## Global Constraints

- No behavior change to the existing UI/Celery flow **except** the single intentional change: wrong-domain form ids report `not_found` (folded with genuinely-missing ids), instead of today's distinct `"XForm {id} does not belong to domain {domain}"` message.
- The shim (`archive_or_restore_forms`) must keep its exact current signature: `archive_or_restore_forms(domain, user_id, username, form_ids, archive_or_restore, task=None, from_excel=False)` and its `{"messages": {...}}` / raw-`from_excel` return shapes.
- Blob helpers use `CODES.bulk_async_job` (= 18, already defined in `corehq/blobs/__init__.py`).
- Blob helpers are built + unit-tested standalone; do **not** wire them into the live shim path in this PR.
- `FormActionResult` reasons emitted in this ticket: `'not_found'`, `'unexpected_error'` only.
- Out of scope: view/worker/poll changes, `delete` action, tombstones, richer reason taxonomy, UI/JS/template changes.
- Branch: `gh/refactor-form-action-core` (stacked on `gh/bulk-async-job`).
- Run tests with `uv run pytest --reusedb=1 <path>`; lint with `uv run ruff check <path>`.

## File Structure

- `corehq/apps/data_interfaces/utils.py` — **modify**: gains `FormActionResult`, `iter_form_action_results`, and the status constants; `archive_or_restore_forms` is rewritten as a shim over the new core.
- `corehq/apps/data_interfaces/blobs.py` — **create**: blob payload helpers for `BulkAsyncJob` (`save_requested_ids` / `read_requested_ids` / `save_skipped_ids` / `read_skipped_ids`).
- `corehq/apps/data_interfaces/tests/test_utils.py` — **modify**: add `TestArchiveOrRestoreForms` (characterization, Task 1) and `TestIterFormActionResults` (core unit tests, Task 3).
- `corehq/apps/data_interfaces/tests/test_blobs.py` — **create**: round-trip unit tests for the blob helpers.

---

## Task 1: Characterization tests for `archive_or_restore_forms`

Pin down today's behavior **before** refactoring. These run green against the current code. They mock the form-fetch boundary (`XFormInstance.objects.iter_forms`) and assert the exact `{"messages": {...}}` output. One assertion (wrong-domain) is intentionally updated in Task 3.

**Files:**
- Modify: `corehq/apps/data_interfaces/tests/test_utils.py`

**Interfaces:**
- Consumes: `corehq.apps.data_interfaces.utils.archive_or_restore_forms`, `corehq.apps.data_interfaces.interfaces.FormManagementMode`.
- Produces: nothing consumed by later tasks (test-only).

- [ ] **Step 1: Add the characterization test class**

Add to the end of `corehq/apps/data_interfaces/tests/test_utils.py`. Add these imports at the top of the file (next to the existing imports):

```python
from corehq.apps.data_interfaces.interfaces import FormManagementMode
from corehq.apps.data_interfaces.utils import archive_or_restore_forms
```

Then append:

```python
class TestArchiveOrRestoreForms(SimpleTestCase):
    """Characterization tests locking current behavior before the SAAS-19975 refactor."""

    USER_ID = 'user-id'
    USERNAME = 'user@example.com'

    def _archive_mode(self):
        return FormManagementMode(FormManagementMode.ARCHIVE_MODE)

    def _restore_mode(self):
        return FormManagementMode(FormManagementMode.RESTORE_MODE)

    def _call(self, mode, form_ids, forms, **kwargs):
        with patch(
            'corehq.apps.data_interfaces.utils.XFormInstance.objects.iter_forms',
            return_value=forms,
        ):
            return archive_or_restore_forms(
                DOMAIN, self.USER_ID, self.USERNAME, form_ids, mode, **kwargs)

    def test_archive_success(self):
        form = Mock(form_id='f1', domain=DOMAIN)
        result = self._call(self._archive_mode(), ['f1'], [form])
        form.archive.assert_called_once_with(user_id=self.USER_ID)
        messages = result['messages']
        assert messages['errors'] == []
        assert messages['success'] == [
            "Successfully archived XForm f1 for domain test-domain "
            "by user 'user@example.com'"
        ]
        assert messages['success_count_msg'] == 'Successfully archived  1 form(s)'

    def test_restore_success(self):
        form = Mock(form_id='f1', domain=DOMAIN)
        result = self._call(self._restore_mode(), ['f1'], [form])
        form.unarchive.assert_called_once_with(user_id=self.USER_ID)
        messages = result['messages']
        assert messages['success'] == [
            "Successfully unarchived XForm f1 for domain test-domain "
            "by user 'user@example.com'"
        ]
        assert messages['success_count_msg'] == 'Successfully restored  1 form(s)'

    def test_missing_form_reported_not_found(self):
        result = self._call(self._archive_mode(), ['missing'], [])
        assert result['messages']['errors'] == ["Could not find XForm missing"]
        assert result['messages']['success'] == []

    def test_wrong_domain_reports_does_not_belong(self):
        # NOTE: updated intentionally in Task 3 (folds into "Could not find XForm f1").
        form = Mock(form_id='f1', domain='other-domain')
        result = self._call(self._archive_mode(), ['f1'], [form])
        form.archive.assert_not_called()
        assert result['messages']['errors'] == [
            "XForm f1 does not belong to domain test-domain"
        ]

    def test_action_exception_reported(self):
        form = Mock(form_id='f1', domain=DOMAIN)
        form.archive.side_effect = Exception('boom')
        result = self._call(self._archive_mode(), ['f1'], [form])
        assert result['messages']['errors'] == [
            "Could not archive XForm f1 for domain test-domain "
            "by user 'user@example.com': boom"
        ]
        assert result['messages']['success'] == []

    def test_from_excel_returns_raw_response(self):
        form = Mock(form_id='f1', domain=DOMAIN)
        result = self._call(self._archive_mode(), ['f1'], [form], from_excel=True)
        assert 'messages' not in result
        assert 'success_count_msg' not in result
        assert result['success'] == [
            "Successfully archived XForm f1 for domain test-domain "
            "by user 'user@example.com'"
        ]
        assert result['errors'] == []
```

Add `SimpleTestCase` to the Django test imports at the top of the file:

```python
from django.test import SimpleTestCase, TestCase
```

- [ ] **Step 2: Run the new tests against current code; expect PASS**

Run: `uv run pytest --reusedb=1 corehq/apps/data_interfaces/tests/test_utils.py::TestArchiveOrRestoreForms -v`
Expected: all 6 tests PASS (they characterize current behavior).

- [ ] **Step 3: Commit**

```bash
git add corehq/apps/data_interfaces/tests/test_utils.py
git commit -m "Add characterization tests for archive_or_restore_forms

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Blob payload helpers for `BulkAsyncJob`

Standalone read/write helpers for the two JSON payloads the cutover will persist. Not wired into the live path here.

**Files:**
- Create: `corehq/apps/data_interfaces/blobs.py`
- Create: `corehq/apps/data_interfaces/tests/test_blobs.py`

**Interfaces:**
- Produces (consumed later by the SAAS-19895 cutover, not by this PR):
  - `save_requested_ids(domain: str, parent_id: str, form_ids: list[str]) -> str` (returns blob key)
  - `read_requested_ids(key: str) -> list[str]`
  - `save_skipped_ids(domain: str, parent_id: str, skipped: list[dict]) -> str` (returns blob key; `skipped` items are `{"id": str, "reason": str}`)
  - `read_skipped_ids(key: str) -> list[dict]`

- [ ] **Step 1: Write the failing round-trip tests**

Create `corehq/apps/data_interfaces/tests/test_blobs.py`:

```python
from corehq.apps.data_interfaces.blobs import (
    read_requested_ids,
    read_skipped_ids,
    save_requested_ids,
    save_skipped_ids,
)
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB

from django.test import TestCase


class TestBulkAsyncJobBlobs(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db = TemporaryFilesystemBlobDB()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        super().tearDownClass()

    def test_requested_ids_round_trip(self):
        key = save_requested_ids('domain', 'parent-1', ['a', 'b', 'c'])
        assert read_requested_ids(key) == ['a', 'b', 'c']

    def test_requested_ids_empty(self):
        key = save_requested_ids('domain', 'parent-1', [])
        assert read_requested_ids(key) == []

    def test_skipped_ids_round_trip(self):
        skipped = [
            {'id': 'a', 'reason': 'not_found'},
            {'id': 'b', 'reason': 'unexpected_error'},
        ]
        key = save_skipped_ids('domain', 'parent-1', skipped)
        assert read_skipped_ids(key) == skipped
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest --reusedb=1 corehq/apps/data_interfaces/tests/test_blobs.py -v`
Expected: FAIL with `ModuleNotFoundError` / `ImportError` (no `blobs` module yet).

- [ ] **Step 3: Implement the blob helpers**

Create `corehq/apps/data_interfaces/blobs.py`:

```python
"""Blob payload helpers for BulkAsyncJob requested/skipped id lists."""
import json
from io import BytesIO

from corehq.blobs import CODES, get_blob_db


def save_requested_ids(domain, parent_id, form_ids):
    """Store the requested ids payload; returns the blob key."""
    return _put(domain, parent_id, {"requested_ids": list(form_ids)})


def read_requested_ids(key):
    return _get(key)["requested_ids"]


def save_skipped_ids(domain, parent_id, skipped):
    """Store the skipped ids payload (list of {"id", "reason"}); returns the blob key."""
    return _put(domain, parent_id, list(skipped))


def read_skipped_ids(key):
    return _get(key)


def _put(domain, parent_id, payload):
    content = BytesIO(json.dumps(payload).encode('utf-8'))
    meta = get_blob_db().put(
        content,
        domain=domain,
        parent_id=parent_id,
        type_code=CODES.bulk_async_job,
    )
    return meta.key


def _get(key):
    with get_blob_db().get(key=key, type_code=CODES.bulk_async_job) as fileobj:
        return json.load(fileobj)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest --reusedb=1 corehq/apps/data_interfaces/tests/test_blobs.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Lint**

Run: `uv run ruff check corehq/apps/data_interfaces/blobs.py corehq/apps/data_interfaces/tests/test_blobs.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add corehq/apps/data_interfaces/blobs.py corehq/apps/data_interfaces/tests/test_blobs.py
git commit -m "Add BulkAsyncJob blob payload helpers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Extract `iter_form_action_results` core and re-implement the shim

Add the pure core + its unit tests, rewrite `archive_or_restore_forms` as a shim over it, and update the single wrong-domain characterization assertion as the documented intentional change.

**Files:**
- Modify: `corehq/apps/data_interfaces/utils.py:66-117` (the current `archive_or_restore_forms`)
- Modify: `corehq/apps/data_interfaces/tests/test_utils.py` (add `TestIterFormActionResults`; update one assertion in `TestArchiveOrRestoreForms`)

**Interfaces:**
- Consumes: `XFormInstance.objects.iter_forms`, `corehq.apps.data_interfaces.interfaces.FormManagementMode`, `soil.DownloadBase`.
- Produces:
  - `FormActionResult` — `@dataclass(frozen=True)` with `form_id: str`, `status: str`, `reason: Optional[str] = None`.
  - Status constants `SUCCEEDED = 'succeeded'`, `SKIPPED = 'skipped'`.
  - `iter_form_action_results(domain, form_ids, action_fn) -> Iterator[FormActionResult]` — `action_fn(xform)` performs the mutation; exceptions are caught and reported as `reason='unexpected_error'`. Cross-domain and missing ids both report `reason='not_found'`.

- [ ] **Step 1: Write the failing unit tests for the core**

Append to `corehq/apps/data_interfaces/tests/test_utils.py`:

```python
class TestIterFormActionResults(SimpleTestCase):

    def _run(self, form_ids, forms, action_fn=None):
        action_fn = action_fn or (lambda xform: None)
        with patch(
            'corehq.apps.data_interfaces.utils.XFormInstance.objects.iter_forms',
            return_value=forms,
        ):
            return list(iter_form_action_results(DOMAIN, form_ids, action_fn))

    def test_empty_form_ids(self):
        assert self._run([], []) == []

    def test_success(self):
        form = Mock(form_id='f1', domain=DOMAIN)
        calls = []
        results = self._run(['f1'], [form], action_fn=calls.append)
        assert calls == [form]
        assert results == [FormActionResult('f1', SUCCEEDED)]

    def test_missing_is_not_found(self):
        results = self._run(['missing'], [])
        assert results == [FormActionResult('missing', SKIPPED, 'not_found')]

    def test_wrong_domain_is_not_found(self):
        form = Mock(form_id='f1', domain='other-domain')
        called = []
        results = self._run(['f1'], [form], action_fn=called.append)
        assert called == []  # action not applied to out-of-domain forms
        assert results == [FormActionResult('f1', SKIPPED, 'not_found')]

    def test_exception_is_unexpected_error(self):
        form = Mock(form_id='f1', domain=DOMAIN)

        def boom(xform):
            raise Exception('boom')

        results = self._run(['f1'], [form], action_fn=boom)
        assert results == [FormActionResult('f1', SKIPPED, 'unexpected_error')]

    def test_mixed_results(self):
        found = Mock(form_id='f1', domain=DOMAIN)
        results = self._run(['f1', 'missing'], [found])
        assert results == [
            FormActionResult('f1', SUCCEEDED),
            FormActionResult('missing', SKIPPED, 'not_found'),
        ]
```

Update the imports at the top of the file to include the new names:

```python
from corehq.apps.data_interfaces.utils import (
    FormActionResult,
    SKIPPED,
    SUCCEEDED,
    archive_or_restore_forms,
    iter_form_action_results,
)
```

- [ ] **Step 2: Run the core tests to verify they fail**

Run: `uv run pytest --reusedb=1 corehq/apps/data_interfaces/tests/test_utils.py::TestIterFormActionResults -v`
Expected: FAIL with `ImportError` (names not defined yet).

- [ ] **Step 3: Implement the core in `utils.py`**

Add near the top of `corehq/apps/data_interfaces/utils.py`, after the existing imports add:

```python
from dataclasses import dataclass
```

Add the status constants and dataclass above `archive_or_restore_forms`:

```python
SUCCEEDED = 'succeeded'
SKIPPED = 'skipped'


@dataclass(frozen=True)
class FormActionResult:
    """Outcome of a bulk form action for a single requested form id."""
    form_id: str
    status: str                      # SUCCEEDED | SKIPPED
    reason: Optional[str] = None     # 'not_found' | 'unexpected_error'; None when succeeded


def iter_form_action_results(domain, form_ids, action_fn):
    """Apply ``action_fn`` to each in-domain form and yield a ``FormActionResult`` per id.

    :param action_fn: callable taking an ``XFormInstance``; performs the mutation.
        Any exception it raises is reported as ``reason='unexpected_error'``.

    Cross-domain and genuinely-missing ids are both reported as ``reason='not_found'``.
    """
    missing_form_ids = set(form_ids)
    for xform in XFormInstance.objects.iter_forms(form_ids):
        if xform.domain != domain:
            continue  # out of scope -> reported as not_found below
        missing_form_ids.discard(xform.form_id)
        try:
            action_fn(xform)
        except Exception:
            yield FormActionResult(xform.form_id, SKIPPED, 'unexpected_error')
        else:
            yield FormActionResult(xform.form_id, SUCCEEDED)
    for form_id in missing_form_ids:
        yield FormActionResult(form_id, SKIPPED, 'not_found')
```

- [ ] **Step 4: Run the core tests to verify they pass**

Run: `uv run pytest --reusedb=1 corehq/apps/data_interfaces/tests/test_utils.py::TestIterFormActionResults -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Rewrite `archive_or_restore_forms` as a shim**

Replace the body of `archive_or_restore_forms` (current `corehq/apps/data_interfaces/utils.py:66-117`) with:

```python
def archive_or_restore_forms(domain, user_id, username, form_ids, archive_or_restore, task=None, from_excel=False):
    response = {
        'errors': [],
        'success': [],
    }
    captured_errors = {}
    is_archive = archive_or_restore.is_archive_mode()

    def action_fn(xform):
        try:
            if is_archive:
                xform.archive(user_id=user_id)
            else:
                xform.unarchive(user_id=user_id)
        except Exception as exc:
            captured_errors[xform.form_id] = exc
            raise

    success_count = 0
    if task:
        DownloadBase.set_progress(task, 0, len(form_ids))

    for result in iter_form_action_results(domain, form_ids, action_fn):
        if result.reason == 'not_found':
            response['errors'].append(
                _("Could not find XForm {form_id}").format(form_id=result.form_id))
            continue

        xform_string = _("XForm {form_id} for domain {domain} by user '{username}'").format(
            form_id=result.form_id,
            domain=domain,
            username=username)

        if result.status == SUCCEEDED:
            if is_archive:
                message = _("Successfully archived {form}").format(form=xform_string)
            else:
                message = _("Successfully unarchived {form}").format(form=xform_string)
            response['success'].append(message)
            success_count = success_count + 1
        else:  # unexpected_error
            response['errors'].append(_("Could not archive {form}: {error}").format(
                form=xform_string, error=captured_errors.get(result.form_id)))

        if task:
            DownloadBase.set_progress(task, success_count, len(form_ids))

    if from_excel:
        return response

    response["success_count_msg"] = _("{success_msg} {count} form(s)".format(
        success_msg=archive_or_restore.success_text,
        count=success_count))
    return {"messages": response}
```

Note: the success message now uses the requested `domain` (not `xform.domain`); these are equal because the core only acts on in-domain forms. The `: {error}` detail is preserved via `captured_errors`, which is the throwaway shim's concern only — `FormActionResult` stays minimal.

- [ ] **Step 6: Update the intentional wrong-domain assertion in the characterization test**

In `TestArchiveOrRestoreForms`, replace `test_wrong_domain_reports_does_not_belong` with the new expected behavior:

```python
    def test_wrong_domain_reports_not_found(self):
        # Intentional SAAS-19975 change: cross-domain ids fold into not_found
        # (indistinguishable from genuinely missing) for API security posture.
        form = Mock(form_id='f1', domain='other-domain')
        result = self._call(self._archive_mode(), ['f1'], [form])
        form.archive.assert_not_called()
        assert result['messages']['errors'] == ["Could not find XForm f1"]
```

- [ ] **Step 7: Run the full data_interfaces utils test module**

Run: `uv run pytest --reusedb=1 corehq/apps/data_interfaces/tests/test_utils.py -v`
Expected: all tests PASS (characterization tests still green with the one updated assertion; core tests green; pre-existing `TestTasks` / payload tests unaffected).

- [ ] **Step 8: Lint and import-sort**

Run: `uv run ruff check corehq/apps/data_interfaces/utils.py corehq/apps/data_interfaces/tests/test_utils.py`
Run: `uv run ruff check --select I --fix corehq/apps/data_interfaces/utils.py corehq/apps/data_interfaces/tests/test_utils.py`
Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add corehq/apps/data_interfaces/utils.py corehq/apps/data_interfaces/tests/test_utils.py
git commit -m "Extract iter_form_action_results core; reimplement archive_or_restore_forms as shim

Folds wrong-domain form ids into not_found (intentional behavior change).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Blob helpers (read/write `requested_ids`/`skipped_ids`) → Task 2. ✓
- Pure core `iter_form_action_results` (no i18n / no `DownloadBase` / no `from_excel`; injected `action_fn`) → Task 3. ✓
- Shim re-implementation preserving `{"messages": ...}` + progress + `from_excel` → Task 3. ✓
- Unit tests for the core → Task 3. ✓
- Characterization tests / existing tests continue to pass → Task 1 + Task 3 Step 7. ✓
- Intentional wrong-domain → `not_found` change, made explicit/reviewable → Task 1 (original) + Task 3 Step 6 (update). ✓
- `FormActionResult` shape (`form_id`/`status`/`reason`, no error field) → Task 3. ✓
- Scope fences (no view/worker/poll, no delete/tombstones) → respected; none of those files are touched. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✓

**Type consistency:** `FormActionResult(form_id, status, reason)`, `SUCCEEDED`/`SKIPPED`, and `iter_form_action_results(domain, form_ids, action_fn)` are used identically across Task 3 implementation and tests. Blob helper names match between `blobs.py` and `test_blobs.py`. ✓

**Open implementation note (flagged in spec):** Preserving the exact `unexpected_error` message text (`: {error}`) is handled by capturing exceptions in the shim's `action_fn` (`captured_errors`), keeping `FormActionResult` minimal. If review prefers an explicit `error` field on `FormActionResult` instead, that is a localized change to Task 3 — confirm before/at Task 3.
