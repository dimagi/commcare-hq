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
