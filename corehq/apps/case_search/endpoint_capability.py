"""Capability metadata for case search endpoints.

Describes which fields, operations, and input shapes are available for a
domain (built from the data dictionary). Query builder filter specs are
parsed and validated against this metadata in :mod:`.filter_spec`.
"""

from django.db.models import Prefetch
from django.utils.translation import gettext_lazy as _

from corehq.apps.data_dictionary.models import (
    CaseProperty,
    CaseType,
)

FIELD_TYPE_TEXT = 'text'
FIELD_TYPE_NUMBER = 'number'
FIELD_TYPE_DATE = 'date'
FIELD_TYPE_DATETIME = 'datetime'
FIELD_TYPE_SELECT = 'select'
FIELD_TYPE_GEOPOINT = 'geopoint'

# DataType -> field type mapping
_DATA_TYPE_MAP = {
    CaseProperty.DataType.PLAIN: FIELD_TYPE_TEXT,
    CaseProperty.DataType.BARCODE: FIELD_TYPE_TEXT,
    CaseProperty.DataType.PHONE_NUMBER: FIELD_TYPE_TEXT,
    CaseProperty.DataType.UNDEFINED: FIELD_TYPE_TEXT,
    CaseProperty.DataType.DATE: FIELD_TYPE_DATE,
    CaseProperty.DataType.NUMBER: FIELD_TYPE_NUMBER,
    CaseProperty.DataType.SELECT: FIELD_TYPE_SELECT,
    CaseProperty.DataType.GPS: FIELD_TYPE_GEOPOINT,
}

# DataTypes excluded from the query builder (not an oversight).
_EXCLUDED_DATA_TYPES = {CaseProperty.DataType.PASSWORD}

# Field type -> available operations as (name, label) pairs.
# `name` is the stable operator identity used by the API and validation;
# `label` is the translatable, type-specific UI string. Labels reuse the
# phrasing from the data cleaning tool (corehq.apps.data_cleaning) so the
# already-translated strings carry over.
# Labels intentionally match the ones in corehq/apps/data_cleaning/models/types.py
_OPERATIONS_BY_TYPE = {
    FIELD_TYPE_TEXT: [
        ('equals', _('is exactly')),
        ('not_equals', _('is not')),
        ('starts_with', _('starts with')),
    ],
    FIELD_TYPE_NUMBER: [
        ('equals', _('equals')),
        ('not_equals', _('does not equal')),
        ('gt', _('greater than')),
        ('gte', _('greater than or equal to')),
        ('lt', _('less than')),
        ('lte', _('less than or equal to')),
    ],
    FIELD_TYPE_DATE: [
        ('equals', _('on')),
        ('lt', _('before')),
        ('gt', _('after')),
    ],
    FIELD_TYPE_DATETIME: [
        ('equals', _('on')),
        ('lt', _('before')),
        ('gt', _('after')),
    ],
    FIELD_TYPE_SELECT: [
        ('selected_any', _('is any')),
        ('selected_all', _('is all')),
        ('is_empty', _('is empty')),
    ],
    FIELD_TYPE_GEOPOINT: [
        ('within_distance', _('within distance')),
    ],
}

# Sentinel input-slot type: the slot has no fixed type of its own and instead
# takes the type of the field the condition is applied to. Used by operators
# shared across field types (e.g. lt/gt work on both numbers and dates), where
# pinning the input to a single concrete type would be wrong. The UI is meant
# to resolve this to the field's type and render the matching input widget
# (e.g. a date picker for a date field); that resolution is not implemented yet.
INPUT_TYPE_MATCH_FIELD = 'match_field'

COMPONENT_INPUT_SCHEMAS = {
    'not_equals': [{'name': 'value', 'type': FIELD_TYPE_TEXT}],
    'starts_with': [{'name': 'value', 'type': FIELD_TYPE_TEXT}],
    'selected_any': [{'name': 'value', 'type': FIELD_TYPE_TEXT}],
    'selected_all': [{'name': 'value', 'type': FIELD_TYPE_TEXT}],
    'is_empty': [],
    'equals': [{'name': 'value', 'type': INPUT_TYPE_MATCH_FIELD}],
    # lt/gt(/lte/gte) are shared by number and date fields, so the input
    # follows the field's own type rather than being pinned to number.
    'gt': [{'name': 'value', 'type': INPUT_TYPE_MATCH_FIELD}],
    'gte': [{'name': 'value', 'type': INPUT_TYPE_MATCH_FIELD}],
    'lt': [{'name': 'value', 'type': INPUT_TYPE_MATCH_FIELD}],
    'lte': [{'name': 'value', 'type': INPUT_TYPE_MATCH_FIELD}],
    'within_distance': [
        {'name': 'point', 'type': FIELD_TYPE_GEOPOINT},
        {'name': 'distance', 'type': FIELD_TYPE_NUMBER},
        {'name': 'unit', 'type': 'choice'},
    ],
}


def get_field_type(data_type):
    """Map a CaseProperty.DataType to a query builder field type.

    Returns ``None`` for intentionally excluded types (e.g. PASSWORD).
    Raises ``ValueError`` for unmapped types — a new ``DataType`` must be
    explicitly added to ``_DATA_TYPE_MAP`` or ``_EXCLUDED_DATA_TYPES``.
    """
    if data_type in _EXCLUDED_DATA_TYPES:
        return None
    field_type = _DATA_TYPE_MAP.get(data_type)
    if field_type is None:
        raise ValueError(f"Unmapped CaseProperty.DataType: {data_type!r}")
    return field_type


def get_operations_for_field_type(field_type):
    """Return the operations available for a field type as {name, label} dicts."""
    return [
        {'name': name, 'label': label}
        for name, label in _OPERATIONS_BY_TYPE.get(field_type, [])
    ]


def get_capability(domain):
    """Build the full capability JSON for a domain from the data dictionary."""
    case_types = CaseType.objects.filter(
        domain=domain,
        is_deprecated=False,
    ).prefetch_related(
        Prefetch(
            'properties',
            queryset=CaseProperty.objects.filter(
                deprecated=False,
            ).prefetch_related('allowed_values'),
            to_attr='active_properties',
        ),
    )

    result_case_types = {}
    for ct in case_types:
        fields = {}
        for prop in ct.active_properties:
            field_type = get_field_type(prop.data_type)
            if field_type is None:
                continue
            field = {
                'name': prop.name,
                'type': field_type,
                'operations': get_operations_for_field_type(field_type),
            }
            if field_type == FIELD_TYPE_SELECT:
                field['options'] = [
                    av.allowed_value for av in prop.allowed_values.all()
                ]
            fields[prop.name] = field
        result_case_types[ct.name] = fields

    return {
        'case_types': result_case_types,
        'component_input_schemas': COMPONENT_INPUT_SCHEMAS,
    }
