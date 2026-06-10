"""Capability metadata for case search endpoints.

Describes which fields, operations, and input shapes are available for a
domain (built from the data dictionary), and validates a query builder
filter spec against that metadata.
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
    # PASSWORD intentionally omitted — returns None
}

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
        ('exact_match', _('is exactly')),
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
    'exact_match': [{'name': 'value', 'type': FIELD_TYPE_TEXT}],
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
    'date_range': [
        {'name': 'start', 'type': INPUT_TYPE_MATCH_FIELD},
        {'name': 'end', 'type': INPUT_TYPE_MATCH_FIELD},
    ],
    'within_distance': [
        {'name': 'point', 'type': FIELD_TYPE_GEOPOINT},
        {'name': 'distance', 'type': FIELD_TYPE_NUMBER},
        {'name': 'unit', 'type': 'choice'},
    ],
}


def get_field_type(data_type):
    """Map a CaseProperty.DataType to a query builder field type.
    Returns None for types that should be excluded (e.g. PASSWORD).
    """
    return _DATA_TYPE_MAP.get(data_type)


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

    result_case_types = []
    for ct in case_types:
        fields = []
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
            fields.append(field)
        result_case_types.append(
            {
                'name': ct.name,
                'fields': fields,
            }
        )

    return {
        'case_types': result_case_types,
        'component_input_schemas': COMPONENT_INPUT_SCHEMAS,
    }


# Maximum nesting depth of and/or groups; `not` wrappers do not count.
MAX_QUERY_DEPTH = 5
# Maximum children per and/or group.
MAX_GROUP_WIDTH = 50
# Maximum total nodes across the entire query tree.
MAX_TOTAL_NODES = 200


def validate_filter_spec(spec, case_type_name, capability):
    """Validate a query builder filter spec against capability metadata.

    Returns a list of error message strings (empty list = valid).
    """
    errors = []
    case_type = next(
        (
            case_type
            for case_type in capability.get('case_types', [])
            if case_type['name'] == case_type_name
        ),
        None,
    )
    fields_by_name = (
        {field['name']: field for field in case_type['fields']}
        if case_type
        else {}
    )

    _validate_node(spec, fields_by_name, errors, counter=[0])
    return errors


def _validate_node(node, fields_by_name, errors, depth=0, counter=None):
    counter[0] += 1
    if counter[0] > MAX_TOTAL_NODES:
        errors.append(f'Query has too many nodes (max {MAX_TOTAL_NODES})')
        return
    if not isinstance(node, dict):
        errors.append(
            f'Invalid node: expected object, got {type(node).__name__}'
        )
        return
    if depth > MAX_QUERY_DEPTH:
        errors.append(
            f'Query is nested too deeply (max {MAX_QUERY_DEPTH} levels)'
        )
        return
    node_type = node.get('type')

    if node_type in ('and', 'or'):
        children = node.get('children', [])
        if len(children) > MAX_GROUP_WIDTH:
            errors.append(
                f'Group has too many conditions (max {MAX_GROUP_WIDTH})'
            )
            return
        for child in children:
            _validate_node(
                child,
                fields_by_name,
                errors,
                depth + 1,
                counter,
            )
    elif node_type == 'not':
        child = node.get('child')
        if not child:
            errors.append("'not' node must have a 'child'")
        elif isinstance(child, dict) and child.get('type') == 'not':
            # Redundant, and bounds recursion since `not` does not add depth.
            errors.append("'not' node cannot directly contain another 'not'")
        else:
            _validate_node(
                child,
                fields_by_name,
                errors,
                depth,
                counter,
            )
    elif node_type == 'component':
        _validate_component(node, fields_by_name, errors)
    else:
        errors.append(
            f"Invalid node type: '{node_type}'. Expected 'and', 'or', 'not', or 'component'."
        )


def _validate_component(node, fields_by_name, errors):
    field_name = node.get('field', '')
    component_name = node.get('component', '')
    inputs = node.get('inputs', {})

    field = fields_by_name.get(field_name)
    if not field:
        errors.append(f"Unknown field: '{field_name}'")
        return

    operation_names = [op['name'] for op in field.get('operations', [])]
    if component_name not in operation_names:
        errors.append(
            f"'{component_name}' is not a valid operation for field '{field_name}' "
            f'(type: {field["type"]})'
        )
        return

    schema = COMPONENT_INPUT_SCHEMAS.get(component_name, [])
    for slot in schema:
        slot_name = slot['name']
        if slot_name not in inputs:
            errors.append(
                f"Missing required input '{slot_name}' for component '{component_name}'"
            )
            continue
        _validate_input_value(inputs[slot_name], slot_name, errors)


def _validate_input_value(value, slot_name, errors):
    value_type = value.get('type')
    if value_type == 'constant':
        pass  # any value accepted
    else:
        errors.append(f"Invalid input type '{value_type}' in '{slot_name}'")
