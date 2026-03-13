from corehq.apps.data_dictionary.models import (
    CaseProperty,
    CaseType,
)

# DataType -> field type mapping
_DATA_TYPE_MAP = {
    CaseProperty.DataType.PLAIN: 'text',
    CaseProperty.DataType.BARCODE: 'text',
    CaseProperty.DataType.PHONE_NUMBER: 'text',
    CaseProperty.DataType.UNDEFINED: 'text',
    CaseProperty.DataType.DATE: 'date',
    CaseProperty.DataType.NUMBER: 'number',
    CaseProperty.DataType.SELECT: 'select',
    CaseProperty.DataType.GPS: 'geopoint',
    # PASSWORD intentionally omitted — returns None
}

# Field type -> available operations
_OPERATIONS_BY_TYPE = {
    'text': [
        'exact_match',
        'not_equals',
        'starts_with',
        'fuzzy_match',
        'phonetic_match',
        'selected_any',
        'selected_all',
        'is_empty',
    ],
    'number': [
        'equals',
        'not_equals',
        'gt',
        'gte',
        'lt',
        'lte',
        'is_empty',
    ],
    'date': [
        'equals',
        'before',
        'after',
        'date_range',
        'fuzzy_date',
        'is_empty',
    ],
    'datetime': [
        'equals',
        'before',
        'after',
        'date_range',
        'is_empty',
    ],
    'select': [
        'selected_any',
        'selected_all',
        'exact_match',
        'is_empty',
    ],
    'geopoint': [
        'within_distance',
    ],
}

COMPONENT_INPUT_SCHEMAS = {
    'exact_match': [{'name': 'value', 'type': 'text'}],
    'not_equals': [{'name': 'value', 'type': 'text'}],
    'starts_with': [{'name': 'value', 'type': 'text'}],
    'fuzzy_match': [{'name': 'value', 'type': 'text'}],
    'phonetic_match': [{'name': 'value', 'type': 'text'}],
    'selected_any': [{'name': 'value', 'type': 'text'}],
    'selected_all': [{'name': 'value', 'type': 'text'}],
    'is_empty': [],
    'equals': [{'name': 'value', 'type': 'match_field'}],
    'gt': [{'name': 'value', 'type': 'number'}],
    'gte': [{'name': 'value', 'type': 'number'}],
    'lt': [{'name': 'value', 'type': 'number'}],
    'lte': [{'name': 'value', 'type': 'number'}],
    'before': [{'name': 'value', 'type': 'match_field'}],
    'after': [{'name': 'value', 'type': 'match_field'}],
    'date_range': [
        {'name': 'start', 'type': 'match_field'},
        {'name': 'end', 'type': 'match_field'},
    ],
    'fuzzy_date': [{'name': 'value', 'type': 'date'}],
    'within_distance': [
        {'name': 'point', 'type': 'geopoint'},
        {'name': 'distance', 'type': 'number'},
        {'name': 'unit', 'type': 'choice'},
    ],
}

_AUTO_VALUES = {
    'date': [
        {'ref': 'today()', 'label': 'Today'},
    ],
    'datetime': [
        {'ref': 'now()', 'label': 'Now'},
    ],
    'text': [
        {'ref': 'user.username', 'label': "Current user's username"},
        {'ref': 'user.uuid', 'label': "Current user's ID"},
        {'ref': 'user.location_ids', 'label': "User's location IDs"},
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
        'properties',
        'properties__allowed_values',
    )

    result_case_types = []
    for ct in case_types:
        fields = []
        for prop in ct.properties.filter(deprecated=False):
            field_type = get_field_type(prop.data_type)
            if field_type is None:
                continue
            field = {
                'name': prop.name,
                'type': field_type,
                'operations': get_operations_for_field_type(field_type),
            }
            if field_type == 'select':
                field['options'] = list(
                    prop.allowed_values.values_list('allowed_value', flat=True)
                )
            fields.append(field)
        result_case_types.append(
            {
                'name': ct.name,
                'fields': fields,
            }
        )

    return {
        'case_types': result_case_types,
        'auto_values': _AUTO_VALUES,
        'component_input_schemas': COMPONENT_INPUT_SCHEMAS,
    }
