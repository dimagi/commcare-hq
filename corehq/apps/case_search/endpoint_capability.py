"""Capability metadata for case search endpoints.

Describes which fields, operations, and input shapes are available for a
domain (built from the data dictionary), and validates a query builder
filter spec against that metadata.
"""

from django.db.models import Prefetch

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

# Field type -> available operations
_OPERATIONS_BY_TYPE = {
    FIELD_TYPE_TEXT: [
        'equals',
        'not_equals',
        'starts_with',
    ],
    FIELD_TYPE_NUMBER: [
        'equals',
        'not_equals',
        'gt',
        'gte',
        'lt',
        'lte',
    ],
    FIELD_TYPE_DATE: [
        'equals',
        'before',
        'after',
    ],
    FIELD_TYPE_DATETIME: [
        'equals',
        'before',
        'after',
    ],
    FIELD_TYPE_SELECT: [
        'selected_any',
        'selected_all',
        'exact_match',
        'is_empty',
    ],
    FIELD_TYPE_GEOPOINT: [
        'within_distance',
    ],
}

COMPONENT_INPUT_SCHEMAS = {
    'exact_match': [{'name': 'value', 'type': FIELD_TYPE_TEXT}],
    'not_equals': [{'name': 'value', 'type': FIELD_TYPE_TEXT}],
    'starts_with': [{'name': 'value', 'type': FIELD_TYPE_TEXT}],
    'selected_any': [{'name': 'value', 'type': FIELD_TYPE_TEXT}],
    'selected_all': [{'name': 'value', 'type': FIELD_TYPE_TEXT}],
    'is_empty': [],
    'equals': [{'name': 'value', 'type': 'match_field'}],
    'gt': [{'name': 'value', 'type': FIELD_TYPE_NUMBER}],
    'gte': [{'name': 'value', 'type': FIELD_TYPE_NUMBER}],
    'lt': [{'name': 'value', 'type': FIELD_TYPE_NUMBER}],
    'lte': [{'name': 'value', 'type': FIELD_TYPE_NUMBER}],
    'before': [{'name': 'value', 'type': 'match_field'}],
    'after': [{'name': 'value', 'type': 'match_field'}],
    'date_range': [
        {'name': 'start', 'type': 'match_field'},
        {'name': 'end', 'type': 'match_field'},
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
    """Return the list of operation names available for a field type."""
    return list(_OPERATIONS_BY_TYPE.get(field_type, []))


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


_MAX_QUERY_DEPTH = 5


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

    _validate_node(spec, fields_by_name, errors)
    return errors


def _validate_node(
    node, fields_by_name, errors, depth=0
):
    if not isinstance(node, dict):
        errors.append(
            f'Invalid node: expected object, got {type(node).__name__}'
        )
        return
    if depth > _MAX_QUERY_DEPTH:
        errors.append(
            f'Query is nested too deeply (max {_MAX_QUERY_DEPTH} levels)'
        )
        return
    node_type = node.get('type')

    if node_type in ('and', 'or'):
        for child in node.get('children', []):
            _validate_node(
                child,
                fields_by_name,
                errors,
                depth + 1,
            )
    elif node_type == 'not':
        child = node.get('child')
        if child:
            _validate_node(
                child,
                fields_by_name,
                errors,
                depth + 1,
            )
        else:
            errors.append("'not' node must have a 'child'")
    elif node_type == 'component':
        _validate_component(
            node, fields_by_name, errors
        )
    else:
        errors.append(
            f"Invalid node type: '{node_type}'. Expected 'and', 'or', 'not', or 'component'."
        )


def _validate_component(
    node, fields_by_name, errors
):
    field_name = node.get('field', '')
    component_name = node.get('component', '')
    inputs = node.get('inputs', {})

    field = fields_by_name.get(field_name)
    if not field:
        errors.append(f"Unknown field: '{field_name}'")
        return

    if component_name not in field.get('operations', []):
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
        _validate_input_value(
            inputs[slot_name], slot_name, errors
        )


def _validate_input_value(
    value, slot_name, errors
):
    value_type = value.get('type')
    if value_type == 'constant':
        pass  # any value accepted
    else:
        errors.append(f"Invalid input type '{value_type}' in '{slot_name}'")
