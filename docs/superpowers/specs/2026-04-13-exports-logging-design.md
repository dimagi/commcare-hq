# Export Download Logging

Spec for [SAAS-19581](https://dimagi.atlassian.net/browse/SAAS-19581).

## Goal

Log a structured summary every time an export is generated, capturing what
was exported, by whom, and with what parameters. Logs ship to CloudWatch
where they are stored for at least 6 years.

## Log placement

A `logging.info` call at the end of `write_export_instance()` in
`corehq/apps/export/export.py`, after the row-writing loop completes and
the row count is known. This location covers both on-demand user downloads
and saved/daily export rebuilds.

## Logging context

Logging-only data (not needed by the export logic itself) is carried in
a namedtuple to keep it cleanly separated in function signatures:

```python
from collections import namedtuple

ExportLoggingContext = namedtuple('ExportLoggingContext', [
    'download_id',  # str or None (None for saved export rebuilds)
    'username',     # str or None (None for saved export rebuilds)
    'trigger',      # "user_download" | "scheduled_rebuild" | "manual_rebuild"
    'filters',      # dict with "active" and "default" keys
])
```

Always construct with named arguments:

```python
logging_context = ExportLoggingContext(
    download_id=download_id,
    username=username,
    trigger="user_download",
    filters=filters,
)
```

## Filter handling

Filter data comes from different sources depending on the trigger:

- **On-demand exports**: Filters originate in the view
  (`prepare_custom_export`) as form data, then get converted to ES query
  objects. The `export_instance.filters` field is empty for on-demand
  exports. The filter summary must be built in the view from the filter
  form data *before* ES conversion, then passed through the task to the
  logging context.
- **Saved export rebuilds**: Filters are stored on
  `export_instance.filters` (a `CaseExportInstanceFilters` or
  `FormExportInstanceFilters` schema). The filter summary is built from
  this schema at `rebuild_export` time.

In both cases, the caller builds the `filters` dict (with `active` and
`default` keys) and puts it in the `ExportLoggingContext`. The log site
just reads `logging_context.filters`.

## Call chain

1. **`prepare_custom_export`** (views/download.py) builds the filter
   summary dict from the filter form data before ES conversion, and passes
   it to `get_export_download`
2. **`populate_export_download_task`** (tasks.py) receives the filter
   summary and builds
   `ExportLoggingContext(download_id=..., username=..., trigger="user_download", filters=...)`
3. **`rebuild_export`** (export.py) builds the filter summary from
   `export_instance.filters` and builds
   `ExportLoggingContext(download_id=None, username=None, trigger="scheduled_rebuild", filters=...)`
   or `trigger="manual_rebuild"` depending on the `manual` parameter
4. Both pass the context to **`get_export_file(..., logging_context=None)`**
5. `get_export_file` computes bulk info from `len(export_instances)` and the
   loop index, then passes both to each
   **`write_export_instance(..., logging_context=None, bulk=None)`** call
6. `write_export_instance` emits the log line after the row-writing loop

## Logger

```python
logger = logging.getLogger("commcare.exports.audit")
```

A new, dedicated logger name so it can be routed and filtered independently.
The existing `export_migration` logger in tasks.py is dead code and will be
cleaned up in a separate PR.

## Log line schema

```json
{
  "event": "export_generated",
  "domain": "my-project",
  "download_id": "dl-abc123",
  "username": "user@example.com",
  "trigger": "user_download",
  "export_type": "case",
  "export_subtype": "patient",
  "export_id": "abc123def456",
  "row_count": 1234,
  "filters": {
    "active": {
      "date_period": {"period_type": "since", "days": 30},
      "users": ["abc123"]
    },
    "default": {
      "can_access_all_locations": true,
      "show_project_data": true,
      "show_all_data": false,
      "show_deactivated_data": false
    }
  },
  "columns": ["name", "dob", "owner_name", "date_opened"],
  "bulk": {"index": 2, "total": 3}
}
```

### Field details

| Field | Source | Notes |
|-------|--------|-------|
| `event` | Constant `"export_generated"` | Identifies log line type |
| `domain` | `export_instance.domain` | |
| `download_id` | `logging_context.download_id` | Null for rebuilds. Matches `dl-` prefix in download URLs for cross-referencing actual downloads |
| `username` | `logging_context.username` | Null for rebuilds |
| `trigger` | `logging_context.trigger` | `"user_download"`, `"scheduled_rebuild"`, or `"manual_rebuild"` |
| `export_type` | `export_instance.type` | `"form"`, `"case"`, or `"sms"` |
| `export_subtype` | `export_instance.xmlns` or `.case_type` | Omitted for SMS exports |
| `export_id` | `export_instance.get_id` | CouchDB document ID |
| `row_count` | `total_rows` from write loop | Already tracked in `write_export_instance` |
| `filters` | `logging_context.filters` | Partitioned into `active` (non-default) and `default` sub-objects. See below |
| `columns` | Selected columns across all selected tables | Flat list of `column.label` strings |
| `bulk` | Computed in `get_export_file` | Omitted for single exports. `{"index": N, "total": M}` for bulk |

### Filter partitioning

Filter fields are split into `active` and `default` based on whether their
value differs from the schema-defined default:

- `ExportInstanceFilters` defaults: `can_access_all_locations=True`,
  empty lists for `users`, `locations`, `reporting_groups`, etc.
- `CaseExportInstanceFilters` adds: `show_project_data=True`,
  `show_all_data=False`, `show_deactivated_data=False`
- `FormExportInstanceFilters` adds:
  `user_types=[HQUserType.ACTIVE, HQUserType.DEACTIVATED]`

A filter field whose value matches its default goes in `default`;
otherwise it goes in `active`.

### Bulk exports

When a user selects multiple exports and clicks "Bulk Export", one
`download_id` is created for all of them. `write_export_instance` is called
once per export instance. Each log line includes the same `download_id` and
a `bulk` field indicating position:

```json
{"event": "export_generated", "export_type": "case", "export_subtype": "patient",  "download_id": "dl-abc", "bulk": {"index": 1, "total": 3}, ...}
{"event": "export_generated", "export_type": "case", "export_subtype": "visit",    "download_id": "dl-abc", "bulk": {"index": 2, "total": 3}, ...}
{"event": "export_generated", "export_type": "case", "export_subtype": "referral", "download_id": "dl-abc", "bulk": {"index": 3, "total": 3}, ...}
```

For single exports, the `bulk` field is omitted entirely.

## Cost estimate

A worst-case log line (100 columns, all filters active) is roughly 3KB.
At CloudWatch ingestion ($0.50/GB) and storage ($0.03/GB/month over 6 years),
even 10,000 exports/day costs a few dollars per year. Column names are
logged as a plain list — no compression needed.
