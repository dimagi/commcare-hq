# Export Download Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured JSON logging when exports are generated, capturing export type, subtype, filters, columns, and row count.

**Architecture:** A `logging.info` call at the end of `write_export_instance()` in `export.py` emits one JSON log line per export instance. Logging-only data (`download_id`, `username`, `trigger`, `filters`) is carried in an `ExportLoggingContext` namedtuple threaded through the call chain. Filter summaries are built at the call site (view for on-demand, `rebuild_export` for saved) and passed in the context.

**Tech Stack:** Python, Django, Celery, logging, JSON

**Spec:** `docs/superpowers/specs/2026-04-13-exports-logging-design.md`

---

### Task 1: Define `ExportLoggingContext` and filter summary builder

**Files:**
- Create: `corehq/apps/export/logging.py`
- Test: `corehq/apps/export/tests/test_export_logging.py`

- [ ] **Step 1: Write the failing test for `ExportLoggingContext`**

```python
# corehq/apps/export/tests/test_export_logging.py
from django.test import SimpleTestCase

from corehq.apps.export.logging import ExportLoggingContext


class TestExportLoggingContext(SimpleTestCase):

    def test_construction_with_named_args(self):
        ctx = ExportLoggingContext(
            download_id="dl-abc123",
            username="user@example.com",
            trigger="user_download",
            filters={"active": {}, "default": {}},
        )
        self.assertEqual(ctx.download_id, "dl-abc123")
        self.assertEqual(ctx.username, "user@example.com")
        self.assertEqual(ctx.trigger, "user_download")
        self.assertEqual(ctx.filters, {"active": {}, "default": {}})

    def test_none_fields_for_rebuilds(self):
        ctx = ExportLoggingContext(
            download_id=None,
            username=None,
            trigger="scheduled_rebuild",
            filters={"active": {}, "default": {}},
        )
        self.assertIsNone(ctx.download_id)
        self.assertIsNone(ctx.username)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest corehq/apps/export/tests/test_export_logging.py -v`
Expected: FAIL — `ImportError: cannot import name 'ExportLoggingContext'`

- [ ] **Step 3: Implement `ExportLoggingContext`**

```python
# corehq/apps/export/logging.py
import json
import logging
from collections import namedtuple

logger = logging.getLogger("commcare.exports.audit")

ExportLoggingContext = namedtuple('ExportLoggingContext', [
    'download_id',
    'username',
    'trigger',
    'filters',
])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest corehq/apps/export/tests/test_export_logging.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for `build_filter_summary`**

This function takes an `ExportInstanceFilters` (or subclass) and returns
a dict with `active` and `default` keys. We need to test it for case,
form, and base filter types.

```python
# Add to corehq/apps/export/tests/test_export_logging.py
from corehq.apps.export.logging import build_filter_summary
from corehq.apps.export.models.new import (
    CaseExportInstanceFilters,
    ExportInstanceFilters,
    FormExportInstanceFilters,
)


class TestBuildFilterSummary(SimpleTestCase):

    def test_all_defaults_case_filters(self):
        filters = CaseExportInstanceFilters()
        result = build_filter_summary(filters)
        self.assertEqual(result["active"], {})
        self.assertEqual(result["default"], {
            "can_access_all_locations": True,
            "accessible_location_ids": [],
            "locations": [],
            "date_period": None,
            "users": [],
            "reporting_groups": [],
            "user_types": [],
            "sharing_groups": [],
            "show_all_data": False,
            "show_project_data": True,
            "show_deactivated_data": False,
        })

    def test_non_default_values_go_to_active(self):
        filters = CaseExportInstanceFilters(
            show_all_data=True,
            users=["user1", "user2"],
        )
        result = build_filter_summary(filters)
        self.assertIn("show_all_data", result["active"])
        self.assertEqual(result["active"]["show_all_data"], True)
        self.assertIn("users", result["active"])
        self.assertEqual(result["active"]["users"], ["user1", "user2"])
        self.assertNotIn("show_all_data", result["default"])
        self.assertNotIn("users", result["default"])

    def test_form_filters_default_user_types(self):
        """FormExportInstanceFilters has a non-empty default for user_types"""
        filters = FormExportInstanceFilters()
        result = build_filter_summary(filters)
        # user_types default is [0, 1] (ACTIVE, DEACTIVATED) — should be in default
        self.assertIn("user_types", result["default"])

    def test_form_filters_non_default_user_types(self):
        filters = FormExportInstanceFilters(user_types=[0])
        result = build_filter_summary(filters)
        self.assertIn("user_types", result["active"])
        self.assertEqual(result["active"]["user_types"], [0])

    def test_none_filters_returns_empty(self):
        result = build_filter_summary(None)
        self.assertEqual(result, {"active": {}, "default": {}})
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest corehq/apps/export/tests/test_export_logging.py::TestBuildFilterSummary -v`
Expected: FAIL — `ImportError: cannot import name 'build_filter_summary'`

- [ ] **Step 7: Implement `build_filter_summary`**

The function needs to know the default values for each filter class.
`ExportInstanceFilters`, `CaseExportInstanceFilters`, and
`FormExportInstanceFilters` are `DocumentSchema` subclasses (from
`dimagi-mage`/couchdbkit). Each property has a `default` defined via its
schema property type. We can get the defaults by constructing an empty
instance of the same class.

```python
# Add to corehq/apps/export/logging.py

# Fields to include in filter summary, per class.
# Order: base fields first, then subclass-specific fields.
_BASE_FILTER_FIELDS = [
    'can_access_all_locations',
    'accessible_location_ids',
    'locations',
    'date_period',
    'users',
    'reporting_groups',
    'user_types',
]

_CASE_FILTER_FIELDS = _BASE_FILTER_FIELDS + [
    'sharing_groups',
    'show_all_data',
    'show_project_data',
    'show_deactivated_data',
]

_FORM_FILTER_FIELDS = _BASE_FILTER_FIELDS  # user_types already in base


def _get_filter_fields(filters):
    from corehq.apps.export.models.new import (
        CaseExportInstanceFilters,
        FormExportInstanceFilters,
    )
    if isinstance(filters, CaseExportInstanceFilters):
        return _CASE_FILTER_FIELDS
    elif isinstance(filters, FormExportInstanceFilters):
        return _FORM_FILTER_FIELDS
    else:
        return _BASE_FILTER_FIELDS


def _serialize_filter_value(value):
    """Convert filter value to a JSON-safe representation."""
    if hasattr(value, 'to_json'):
        return value.to_json()
    return value


def build_filter_summary(filters):
    """Build a dict with 'active' and 'default' keys from an ExportInstanceFilters.

    A filter field whose current value matches the default goes in 'default';
    otherwise it goes in 'active'.
    """
    if filters is None:
        return {"active": {}, "default": {}}

    defaults = type(filters)()
    fields = _get_filter_fields(filters)

    active = {}
    default = {}
    for field in fields:
        current = _serialize_filter_value(getattr(filters, field))
        default_val = _serialize_filter_value(getattr(defaults, field))
        if current == default_val:
            default[field] = current
        else:
            active[field] = current

    return {"active": active, "default": default}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest corehq/apps/export/tests/test_export_logging.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add corehq/apps/export/logging.py corehq/apps/export/tests/test_export_logging.py
git commit -m "Add ExportLoggingContext and build_filter_summary for export audit logging"
```

---

### Task 2: Add `build_export_log_data` and `log_export_generated`

These functions build the full JSON log payload from an export instance
and logging context, then emit it via `logging.info`.

**Files:**
- Modify: `corehq/apps/export/logging.py`
- Test: `corehq/apps/export/tests/test_export_logging.py`

- [ ] **Step 1: Write the failing test for `build_export_log_data`**

```python
# Add to corehq/apps/export/tests/test_export_logging.py
from corehq.apps.export.logging import build_export_log_data
from corehq.apps.export.models import (
    MAIN_TABLE,
    CaseExportInstance,
    ExportColumn,
    ExportItem,
    FormExportInstance,
    PathNode,
    SMSExportInstance,
    TableConfiguration,
)


class TestBuildExportLogData(SimpleTestCase):

    def _make_case_export(self, case_type="patient", columns=None):
        columns = columns or [
            ExportColumn(label="name", item=ExportItem(path=[PathNode(name="name")]), selected=True),
            ExportColumn(label="dob", item=ExportItem(path=[PathNode(name="dob")]), selected=True),
            ExportColumn(label="hidden", item=ExportItem(path=[PathNode(name="hidden")]), selected=False),
        ]
        return CaseExportInstance(
            domain="test-domain",
            case_type=case_type,
            tables=[TableConfiguration(
                label="Cases",
                path=MAIN_TABLE,
                selected=True,
                columns=columns,
            )],
        )

    def _make_form_export(self, xmlns="http://example.com/form"):
        return FormExportInstance(
            domain="test-domain",
            xmlns=xmlns,
            tables=[TableConfiguration(
                label="Forms",
                path=MAIN_TABLE,
                selected=True,
                columns=[
                    ExportColumn(label="q1", item=ExportItem(path=[PathNode(name="q1")]), selected=True),
                ],
            )],
        )

    def _make_context(self, **overrides):
        defaults = {
            "download_id": "dl-test123",
            "username": "testuser@example.com",
            "trigger": "user_download",
            "filters": {"active": {}, "default": {}},
        }
        defaults.update(overrides)
        return ExportLoggingContext(**defaults)

    def test_case_export_fields(self):
        export = self._make_case_export()
        ctx = self._make_context()
        data = build_export_log_data(export, ctx, row_count=42)

        self.assertEqual(data["event"], "export_generated")
        self.assertEqual(data["domain"], "test-domain")
        self.assertEqual(data["download_id"], "dl-test123")
        self.assertEqual(data["username"], "testuser@example.com")
        self.assertEqual(data["trigger"], "user_download")
        self.assertEqual(data["export_type"], "case")
        self.assertEqual(data["export_subtype"], "patient")
        self.assertEqual(data["row_count"], 42)
        self.assertEqual(data["columns"], ["name", "dob"])
        self.assertNotIn("bulk", data)

    def test_form_export_subtype_is_xmlns(self):
        export = self._make_form_export(xmlns="http://example.com/myform")
        ctx = self._make_context()
        data = build_export_log_data(export, ctx, row_count=10)

        self.assertEqual(data["export_type"], "form")
        self.assertEqual(data["export_subtype"], "http://example.com/myform")

    def test_sms_export_no_subtype(self):
        export = SMSExportInstance(domain="test-domain", tables=[])
        ctx = self._make_context()
        data = build_export_log_data(export, ctx, row_count=5)

        self.assertEqual(data["export_type"], "sms")
        self.assertNotIn("export_subtype", data)

    def test_only_selected_columns_included(self):
        export = self._make_case_export()
        ctx = self._make_context()
        data = build_export_log_data(export, ctx, row_count=0)

        self.assertIn("name", data["columns"])
        self.assertIn("dob", data["columns"])
        self.assertNotIn("hidden", data["columns"])

    def test_columns_from_multiple_selected_tables(self):
        export = CaseExportInstance(
            domain="test-domain",
            case_type="patient",
            tables=[
                TableConfiguration(
                    label="Main",
                    path=MAIN_TABLE,
                    selected=True,
                    columns=[
                        ExportColumn(label="name", item=ExportItem(path=[PathNode(name="name")]), selected=True),
                    ],
                ),
                TableConfiguration(
                    label="History",
                    path=[PathNode(name="history")],
                    selected=True,
                    columns=[
                        ExportColumn(label="action", item=ExportItem(path=[PathNode(name="action")]), selected=True),
                    ],
                ),
                TableConfiguration(
                    label="Unselected",
                    path=[PathNode(name="other")],
                    selected=False,
                    columns=[
                        ExportColumn(label="ignored", item=ExportItem(path=[PathNode(name="ignored")]), selected=True),
                    ],
                ),
            ],
        )
        ctx = self._make_context()
        data = build_export_log_data(export, ctx, row_count=0)

        self.assertEqual(data["columns"], ["name", "action"])

    def test_bulk_info_included(self):
        export = self._make_case_export()
        ctx = self._make_context()
        data = build_export_log_data(export, ctx, row_count=0, bulk={"index": 2, "total": 3})

        self.assertEqual(data["bulk"], {"index": 2, "total": 3})

    def test_bulk_omitted_when_none(self):
        export = self._make_case_export()
        ctx = self._make_context()
        data = build_export_log_data(export, ctx, row_count=0, bulk=None)

        self.assertNotIn("bulk", data)

    def test_none_context_still_works(self):
        export = self._make_case_export()
        data = build_export_log_data(export, None, row_count=10)

        self.assertEqual(data["event"], "export_generated")
        self.assertIsNone(data["download_id"])
        self.assertIsNone(data["username"])
        self.assertIsNone(data["trigger"])
        self.assertEqual(data["filters"], {"active": {}, "default": {}})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest corehq/apps/export/tests/test_export_logging.py::TestBuildExportLogData -v`
Expected: FAIL — `ImportError: cannot import name 'build_export_log_data'`

- [ ] **Step 3: Implement `build_export_log_data` and `log_export_generated`**

```python
# Add to corehq/apps/export/logging.py

from corehq.apps.export.const import FORM_EXPORT, CASE_EXPORT


def _get_export_subtype(export_instance):
    if export_instance.type == FORM_EXPORT:
        return export_instance.xmlns
    elif export_instance.type == CASE_EXPORT:
        return export_instance.case_type
    return None


def _get_selected_column_labels(export_instance):
    columns = []
    for table in export_instance.tables:
        if table.selected:
            columns.extend(col.label for col in table.columns if col.selected)
    return columns


def build_export_log_data(export_instance, logging_context, row_count, bulk=None):
    """Build the structured dict for the export audit log line."""
    if logging_context is not None:
        download_id = logging_context.download_id
        username = logging_context.username
        trigger = logging_context.trigger
        filters = logging_context.filters
    else:
        download_id = None
        username = None
        trigger = None
        filters = {"active": {}, "default": {}}

    data = {
        "event": "export_generated",
        "domain": export_instance.domain,
        "download_id": download_id,
        "username": username,
        "trigger": trigger,
        "export_type": export_instance.type,
        "export_id": export_instance.get_id,
        "row_count": row_count,
        "filters": filters,
        "columns": _get_selected_column_labels(export_instance),
    }

    subtype = _get_export_subtype(export_instance)
    if subtype is not None:
        data["export_subtype"] = subtype

    if bulk is not None:
        data["bulk"] = bulk

    return data


def log_export_generated(export_instance, logging_context, row_count, bulk=None):
    """Emit a structured JSON audit log line for a generated export."""
    data = build_export_log_data(export_instance, logging_context, row_count, bulk)
    logger.info(json.dumps(data))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest corehq/apps/export/tests/test_export_logging.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add corehq/apps/export/logging.py corehq/apps/export/tests/test_export_logging.py
git commit -m "Add build_export_log_data and log_export_generated for export audit logging"
```

---

### Task 3: Thread logging context through `write_export_instance` and `get_export_file`

Wire the logging call into the export generation pipeline and thread the
`logging_context` and `bulk` parameters through.

**Files:**
- Modify: `corehq/apps/export/export.py:289-320` (`get_export_download`, `get_export_file`)
- Modify: `corehq/apps/export/export.py:346-411` (`write_export_instance`)
- Test: `corehq/apps/export/tests/test_export_logging.py`

- [ ] **Step 1: Write the failing test**

Test that `write_export_instance` calls `log_export_generated` with the
correct arguments.

```python
# Add to corehq/apps/export/tests/test_export_logging.py
from unittest.mock import patch, call


class TestWriteExportInstanceLogging(SimpleTestCase):

    def _make_simple_export(self):
        return FormExportInstance(
            domain="test-domain",
            xmlns="http://example.com/form",
            tables=[TableConfiguration(
                label="Forms",
                path=MAIN_TABLE,
                selected=True,
                columns=[
                    ExportColumn(
                        label="q1",
                        item=ExportItem(path=[PathNode(name="q1")]),
                        selected=True,
                    ),
                ],
            )],
        )

    @patch('corehq.apps.export.export.log_export_generated')
    @patch('corehq.apps.export.models.FormExportInstance.save')
    def test_logging_called_after_write(self, mock_save, mock_log):
        from corehq.apps.export.export import get_export_writer, write_export_instance
        from corehq.util.files import TransientTempfile

        export = self._make_simple_export()
        docs = [{"domain": "test-domain", "_id": "1", "form": {"q1": "val"}}]
        ctx = ExportLoggingContext(
            download_id="dl-abc",
            username="user@test.com",
            trigger="user_download",
            filters={"active": {}, "default": {}},
        )

        with TransientTempfile() as temp_path:
            writer = get_export_writer([export], temp_path)
            with writer.open([export]):
                write_export_instance(writer, export, docs, logging_context=ctx)

        mock_log.assert_called_once()
        args = mock_log.call_args
        self.assertEqual(args.kwargs["export_instance"], export)
        self.assertEqual(args.kwargs["logging_context"], ctx)
        self.assertEqual(args.kwargs["row_count"], 1)
        self.assertIsNone(args.kwargs["bulk"])

    @patch('corehq.apps.export.export.log_export_generated')
    @patch('corehq.apps.export.models.FormExportInstance.save')
    def test_logging_not_called_when_no_context(self, mock_save, mock_log):
        from corehq.apps.export.export import get_export_writer, write_export_instance
        from corehq.util.files import TransientTempfile

        export = self._make_simple_export()
        docs = [{"domain": "test-domain", "_id": "1", "form": {"q1": "val"}}]

        with TransientTempfile() as temp_path:
            writer = get_export_writer([export], temp_path)
            with writer.open([export]):
                write_export_instance(writer, export, docs)

        mock_log.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest corehq/apps/export/tests/test_export_logging.py::TestWriteExportInstanceLogging -v`
Expected: FAIL — `write_export_instance` doesn't accept `logging_context`

- [ ] **Step 3: Add `logging_context` and `bulk` params to `write_export_instance`**

In `corehq/apps/export/export.py`, modify `write_export_instance`
(currently at line 346):

Change the signature from:

```python
def write_export_instance(writer, export_instance, documents,
                          progress_tracker=None, include_hyperlinks=True):
```

to:

```python
def write_export_instance(writer, export_instance, documents,
                          progress_tracker=None, include_hyperlinks=True,
                          logging_context=None, bulk=None):
```

Add the import at the top of `export.py`:

```python
from corehq.apps.export.logging import log_export_generated
```

Add the logging call at the end of `write_export_instance`, after the
existing metrics recording (after the line
`_record_export_duration(end - start, export_instance)`, currently at
line 410). Add:

```python
    if logging_context is not None:
        log_export_generated(
            export_instance=export_instance,
            logging_context=logging_context,
            row_count=total_rows,
            bulk=bulk,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest corehq/apps/export/tests/test_export_logging.py::TestWriteExportInstanceLogging -v`
Expected: PASS

- [ ] **Step 5: Add `logging_context` param to `get_export_file`**

Modify `get_export_file` in `corehq/apps/export/export.py` (currently at
line 306).

Change the signature from:

```python
def get_export_file(export_instances, es_filters, temp_path,
                    progress_tracker=None, include_hyperlinks=True):
```

to:

```python
def get_export_file(export_instances, es_filters, temp_path,
                    progress_tracker=None, include_hyperlinks=True,
                    logging_context=None):
```

Update the body to compute bulk info and pass it through:

```python
def get_export_file(export_instances, es_filters, temp_path,
                    progress_tracker=None, include_hyperlinks=True,
                    logging_context=None):
    """
    Return an export file for the given ExportInstance and list of filters
    """
    writer = get_export_writer(export_instances, temp_path)
    is_bulk = len(export_instances) > 1

    with writer.open(export_instances):
        for i, export_instance in enumerate(export_instances):
            docs = get_export_documents(export_instance, es_filters)
            bulk = {"index": i + 1, "total": len(export_instances)} if is_bulk else None
            write_export_instance(writer, export_instance, docs,
                                  progress_tracker,
                                  include_hyperlinks=include_hyperlinks,
                                  logging_context=logging_context,
                                  bulk=bulk)

    return ExportFile(writer.path, writer.format)
```

- [ ] **Step 6: Run existing tests to check for regressions**

Run: `uv run pytest corehq/apps/export/tests/test_get_export_file.py -v --reusedb=1`
Expected: All existing tests PASS (no signature breakage since new params
have defaults)

Also run: `uv run pytest corehq/apps/export/tests/test_export.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add corehq/apps/export/export.py corehq/apps/export/tests/test_export_logging.py
git commit -m "Thread logging_context through get_export_file and write_export_instance"
```

---

### Task 4: Wire up on-demand export path (`populate_export_download_task`)

Build the filter summary in `prepare_custom_export`, pass it through
`get_export_download` and `populate_export_download_task`, and construct
the `ExportLoggingContext`.

**Files:**
- Modify: `corehq/apps/export/views/download.py:303-361` (`prepare_custom_export`)
- Modify: `corehq/apps/export/export.py:289-303` (`get_export_download`)
- Modify: `corehq/apps/export/tasks.py:42-104` (`populate_export_download_task`)

- [ ] **Step 1: Add `build_filter_summary_from_form_data` to `logging.py`**

For on-demand exports, filter data comes from the filter form, not from
`export_instance.filters`. The view has `filter_form.cleaned_data` with
date range info and the raw `filter_form_data` with user/group slugs. We
need a function to build the filter summary from what the view has.

The simplest approach: the view passes `filter_form_data` (the raw dict
from the request) as the filter summary. This is the data the user
submitted — date range, user/group selections — and is already a
JSON-serializable dict.

Add to `corehq/apps/export/logging.py`:

```python
def build_filter_summary_from_form_data(filter_form_data):
    """Build a filter summary from the on-demand export filter form data.

    For on-demand exports, the user-selected filters come from the form
    submission, not from export_instance.filters. We log the raw form
    data as the 'active' filters since every filter the user submitted
    represents an active choice.
    """
    if not filter_form_data:
        return {"active": {}, "default": {}}
    return {"active": filter_form_data, "default": {}}
```

- [ ] **Step 2: Modify `get_export_download` to accept and forward `filter_summary`**

In `corehq/apps/export/export.py`, change `get_export_download` from:

```python
def get_export_download(domain, export_ids, exports_type, username, es_filters, owner_id, filename=None):
    from corehq.apps.export.tasks import populate_export_download_task

    download = DownloadBase()
    download.set_task(populate_export_download_task.delay(
        domain,
        export_ids,
        exports_type,
        username,
        es_filters,
        download.download_id,
        owner_id,
        filename=filename
    ))
    return download
```

to:

```python
def get_export_download(domain, export_ids, exports_type, username, es_filters, owner_id,
                        filename=None, filter_summary=None):
    from corehq.apps.export.tasks import populate_export_download_task

    download = DownloadBase()
    download.set_task(populate_export_download_task.delay(
        domain,
        export_ids,
        exports_type,
        username,
        es_filters,
        download.download_id,
        owner_id,
        filename=filename,
        filter_summary=filter_summary,
    ))
    return download
```

- [ ] **Step 3: Modify `populate_export_download_task` to build context and pass it**

In `corehq/apps/export/tasks.py`, change the task signature from:

```python
@task(queue=EXPORT_DOWNLOAD_QUEUE)
def populate_export_download_task(domain, export_ids, exports_type, username,
                                  es_filters, download_id, owner_id,
                                  filename=None, expiry=10 * 60):
```

to:

```python
@task(queue=EXPORT_DOWNLOAD_QUEUE)
def populate_export_download_task(domain, export_ids, exports_type, username,
                                  es_filters, download_id, owner_id,
                                  filename=None, expiry=10 * 60,
                                  filter_summary=None):
```

Add the import near the top of `tasks.py`:

```python
from corehq.apps.export.logging import ExportLoggingContext
```

Inside the task body, after `export_instances` is built (after the line
`for export_id in export_ids]`), build the logging context:

```python
    logging_context = ExportLoggingContext(
        download_id=download_id,
        username=username,
        trigger="user_download",
        filters=filter_summary or {"active": {}, "default": {}},
    )
```

Then pass it to `get_export_file`:

```python
        export_file = get_export_file(
            export_instances,
            es_filters,
            temp_path,
            progress_tracker=populate_export_download_task if len(export_instances) == 1 else None,
            logging_context=logging_context,
        )
```

- [ ] **Step 4: Modify `prepare_custom_export` to build and pass filter summary**

In `corehq/apps/export/views/download.py`, add the import:

```python
from corehq.apps.export.logging import build_filter_summary_from_form_data
```

In `prepare_custom_export`, after `filter_form_data` is parsed (after
line 318), build the summary:

```python
    filter_summary = build_filter_summary_from_form_data(filter_form_data)
```

Then pass it to `get_export_download` (modify the existing call):

```python
    download = get_export_download(
        domain,
        export_ids,
        view_helper.model,
        request.couch_user.username,
        es_filters=export_es_filters,
        owner_id=request.couch_user.get_id,
        filename=filename,
        filter_summary=filter_summary,
    )
```

- [ ] **Step 5: Run existing tests to check for regressions**

Run: `uv run pytest corehq/apps/export/tests/test_export.py corehq/apps/export/tests/test_get_export_file.py corehq/apps/export/tests/test_export_logging.py -v --reusedb=1`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add corehq/apps/export/logging.py corehq/apps/export/export.py corehq/apps/export/tasks.py corehq/apps/export/views/download.py
git commit -m "Wire up export audit logging for on-demand downloads"
```

---

### Task 5: Wire up saved/daily export rebuild path

Thread logging context through `rebuild_export` and `_start_export_task`.

**Files:**
- Modify: `corehq/apps/export/export.py:448-466` (`rebuild_export`)
- Modify: `corehq/apps/export/tasks.py:107-141` (`_start_export_task`, `rebuild_saved_export`)

- [ ] **Step 1: Modify `rebuild_export` to build and pass logging context**

In `corehq/apps/export/export.py`, add the import:

```python
from corehq.apps.export.logging import ExportLoggingContext, build_filter_summary
```

Change `rebuild_export` from:

```python
@metrics_track_errors('rebuild_export')
def rebuild_export(export_instance, progress_tracker):
```

to:

```python
@metrics_track_errors('rebuild_export')
def rebuild_export(export_instance, progress_tracker, manual=False):
```

Inside `rebuild_export`, after the `es_filters` line (currently
`es_filters = [f.to_es_filter() for f in filters]`), build the context:

```python
    logging_context = ExportLoggingContext(
        download_id=None,
        username=None,
        trigger="manual_rebuild" if manual else "scheduled_rebuild",
        filters=build_filter_summary(export_instance.filters),
    )
```

Then pass it to the `get_export_file` call:

```python
        export_file = get_export_file([export_instance], es_filters, temp_path,
                                      progress_tracker,
                                      include_hyperlinks=include_hyperlinks,
                                      logging_context=logging_context)
```

- [ ] **Step 2: Thread `manual` through `_start_export_task`**

In `corehq/apps/export/tasks.py`, change `_start_export_task` from:

```python
@task(queue=SAVED_EXPORTS_QUEUE, ignore_result=False, acks_late=True)
def _start_export_task(export_instance_id):
    export_instance = get_properly_wrapped_export_instance(export_instance_id)
    rebuild_export(export_instance, progress_tracker=_start_export_task)
```

to:

```python
@task(queue=SAVED_EXPORTS_QUEUE, ignore_result=False, acks_late=True)
def _start_export_task(export_instance_id, manual=False):
    export_instance = get_properly_wrapped_export_instance(export_instance_id)
    rebuild_export(export_instance, progress_tracker=_start_export_task, manual=manual)
```

- [ ] **Step 3: Pass `manual` from `rebuild_saved_export` to `_start_export_task`**

In `corehq/apps/export/tasks.py`, change `rebuild_saved_export`
(currently at line 122). Find the `_start_export_task.apply_async` call:

```python
    download_data.set_task(
        _start_export_task.apply_async(
            args=[export_instance_id],
            queue=EXPORT_DOWNLOAD_QUEUE if manual else SAVED_EXPORTS_QUEUE,
        )
    )
```

Change to:

```python
    download_data.set_task(
        _start_export_task.apply_async(
            args=[export_instance_id],
            kwargs={"manual": manual},
            queue=EXPORT_DOWNLOAD_QUEUE if manual else SAVED_EXPORTS_QUEUE,
        )
    )
```

- [ ] **Step 4: Run existing tests to check for regressions**

Run: `uv run pytest corehq/apps/export/tests/ -v --reusedb=1 -x`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add corehq/apps/export/export.py corehq/apps/export/tasks.py
git commit -m "Wire up export audit logging for saved/daily export rebuilds"
```

---

### Task 6: Lint, format, and verify full test suite

**Files:**
- All files modified in previous tasks

- [ ] **Step 1: Run ruff check on all modified files**

```bash
uv run ruff check corehq/apps/export/logging.py corehq/apps/export/export.py corehq/apps/export/tasks.py corehq/apps/export/views/download.py corehq/apps/export/tests/test_export_logging.py
```

Fix any issues found.

- [ ] **Step 2: Run ruff format on all modified files**

```bash
uv run ruff check --select I --fix corehq/apps/export/logging.py corehq/apps/export/export.py corehq/apps/export/tasks.py corehq/apps/export/views/download.py corehq/apps/export/tests/test_export_logging.py
uv run ruff format corehq/apps/export/logging.py corehq/apps/export/export.py corehq/apps/export/tasks.py corehq/apps/export/views/download.py corehq/apps/export/tests/test_export_logging.py
```

- [ ] **Step 3: Run the full export test suite**

```bash
uv run pytest corehq/apps/export/tests/ -v --reusedb=1
```

Expected: All PASS

- [ ] **Step 4: Commit formatting changes if any**

```bash
git add -u corehq/apps/export/
git diff --cached --quiet || git commit -m "Format and lint export audit logging code"
```

(This will only commit if there are staged changes.)
