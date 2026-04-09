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
SCHEMA = 'schema'
TO_SQL = 'toSql'

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
        'exact_match', 'not_equals', 'starts_with', 'fuzzy_match',
        'phonetic_match', 'selected_any', 'selected_all', 'is_empty',
    ],
    FIELD_TYPE_NUMBER: [
        'equals', 'not_equals', 'gt', 'gte', 'lt', 'lte', 'is_empty',
    ],
    FIELD_TYPE_DATE: [
        'equals', 'before', 'after', 'date_range', 'fuzzy_date', 'is_empty',
    ],
    FIELD_TYPE_DATETIME: [
        'equals', 'before', 'after', 'date_range', 'is_empty',
    ],
    FIELD_TYPE_SELECT: [
        'selected_any', 'selected_all', 'exact_match', 'is_empty',
    ],
    FIELD_TYPE_GEOPOINT: [
        'within_distance',
    ],
}

COMPONENT_INPUT_SCHEMAS_AND_FUNCTIONS = {
    'exact_match': {
        SCHEMA: [{'name': 'value', 'type': FIELD_TYPE_TEXT}],
        TO_SQL: lambda field, inputs: f"\"prop__{field}\" = '{inputs['value']}'"
    },
    'not_equals': {
        SCHEMA: [{'name': 'value', 'type': FIELD_TYPE_TEXT}],
        TO_SQL: lambda field, inputs: f"\"prop__{field}\" != '{inputs['value']}'"
    },
    'starts_with': {
        SCHEMA: [{'name': 'value', 'type': FIELD_TYPE_TEXT}],
        TO_SQL: lambda field, inputs: f"\"prop__{field}\" LIKE '{inputs['value']}%'"
    },
    'fuzzy_match': {
        SCHEMA: [{'name': 'value', 'type': FIELD_TYPE_TEXT}],
        TO_SQL: lambda field, inputs: 'not implemented'
    },
    'phonetic_match': {
        SCHEMA: [{'name': 'value', 'type': FIELD_TYPE_TEXT}],
        TO_SQL: lambda field, inputs: 'not implemented'
    },
    'selected_any': {
        SCHEMA: [{'name': 'value', 'type': FIELD_TYPE_TEXT}],
        TO_SQL: lambda field, inputs: 'not implemented'
    },
    'selected_all': {
        SCHEMA: [{'name': 'value', 'type': FIELD_TYPE_TEXT}],
        TO_SQL: lambda field, inputs: 'not implemented'
    },
    'is_empty': {
        SCHEMA: [],
        TO_SQL: lambda field, inputs: f"(\"prop__{field}\" = '' OR \"prop__{field}\" IS NULL)"
    },
    'equals': {
        SCHEMA: [{'name': 'value', 'type': 'match_field'}],
        TO_SQL: lambda field, inputs: f"\"prop__{field}__numeric\" = {inputs['value']}"
    },
    'gt': {
        SCHEMA: [{'name': 'value', 'type': FIELD_TYPE_NUMBER}],
        TO_SQL: lambda field, inputs: f"\"prop__{field}__numeric\" > {inputs['value']}"
    },
    'gte': {
        SCHEMA: [{'name': 'value', 'type': FIELD_TYPE_NUMBER}],
        TO_SQL: lambda field, inputs: f"\"prop__{field}__numeric\" >= {inputs['value']}"
    },
    'lt': {
        SCHEMA: [{'name': 'value', 'type': FIELD_TYPE_NUMBER}],
        TO_SQL: lambda field, inputs: f"\"prop__{field}__numeric\" < {inputs['value']}"
    },
    'lte': {
        SCHEMA: [{'name': 'value', 'type': FIELD_TYPE_NUMBER}],
        TO_SQL: lambda field, inputs: f"\"prop__{field}__numeric\" <= {inputs['value']}"
    },
    'before': {
        SCHEMA: [{'name': 'value', 'type': 'match_field'}],
        TO_SQL: lambda field, inputs: f"\"prop__{field}__date\" < '{inputs['value']}'"
    },
    'after': {
        SCHEMA: [{'name': 'value', 'type': 'match_field'}],
        TO_SQL: lambda field, inputs: f"\"prop__{field}__date\" > '{inputs['value']}'"
    },
    'date_range': {
        SCHEMA: [{'name': 'start', 'type': 'match_field'},
                 {'name': 'end', 'type': 'match_field'}],
        TO_SQL: lambda field, inputs: (
            f"\"prop__{field}__date\" > '{inputs['start']}'"
            f" and \"prop__{field}__date\" < '{inputs['end']}'"
        )
    },
    'fuzzy_date': {
        SCHEMA: [{'name': 'value', 'type': FIELD_TYPE_DATE}],
        TO_SQL: lambda field, inputs: 'not implemented'
    },
    'within_distance': {
        SCHEMA: [{'name': 'point', 'type': FIELD_TYPE_GEOPOINT},
                 {'name': 'distance', 'type': FIELD_TYPE_NUMBER},
                 {'name': 'unit', 'type': 'choice'}],
        TO_SQL: lambda field, inputs: 'not implemented'
    },
}

COMPONENT_INPUT_SCHEMAS = { k: v[SCHEMA] for k, v in COMPONENT_INPUT_SCHEMAS_AND_FUNCTIONS.items() }
COMPONENT_INPUT_FUNCTIONS = { k: v[TO_SQL] for k, v in COMPONENT_INPUT_SCHEMAS_AND_FUNCTIONS.items() }

_AUTO_VALUES = {
    FIELD_TYPE_DATE: [
        {'ref': 'today()', 'label': 'Today'},
    ],
    FIELD_TYPE_DATETIME: [
        {'ref': 'now()', 'label': 'Now'},
    ],
    FIELD_TYPE_TEXT: [
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
            if field_type == FIELD_TYPE_SELECT:
                field['options'] = list(
                    prop.allowed_values.values_list('allowed_value', flat=True)
                )
            fields.append(field)
        result_case_types.append({
            'name': ct.name,
            'fields': fields,
        })

    return {
        'case_types': result_case_types,
        'auto_values': _AUTO_VALUES,
        'component_input_schemas': COMPONENT_INPUT_SCHEMAS,
    }
