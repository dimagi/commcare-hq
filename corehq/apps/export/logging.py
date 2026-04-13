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


def _get_export_subtype(export_instance):
    from corehq.apps.export.const import CASE_EXPORT, FORM_EXPORT
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
