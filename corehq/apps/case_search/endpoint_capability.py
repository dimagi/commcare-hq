from corehq.apps.data_dictionary.models import CaseProperty, CaseType


DATATYPE_TO_FIELD_TYPE = {
    CaseProperty.DataType.DATE: 'date',
    CaseProperty.DataType.PLAIN: 'text',
    CaseProperty.DataType.NUMBER: 'number',
    CaseProperty.DataType.SELECT: 'select',
    CaseProperty.DataType.BARCODE: 'text',
    CaseProperty.DataType.GPS: 'geopoint',
    CaseProperty.DataType.PHONE_NUMBER: 'text',
    CaseProperty.DataType.UNDEFINED: 'text',
    # PASSWORD intentionally excluded
}

OPERATIONS_BY_FIELD_TYPE = {
    'text': [
        'exact_match', 'not_equals', 'starts_with',
        'fuzzy_match', 'phonetic_match', 'is_empty',
    ],
    'number': [
        'equals', 'not_equals', 'gt', 'gte', 'lt', 'lte', 'is_empty',
    ],
    'date': [
        'equals', 'before', 'after', 'date_range', 'fuzzy_date', 'is_empty',
    ],
    'select': [
        'selected_any', 'selected_all', 'exact_match', 'is_empty',
    ],
    'geopoint': [
        'within_distance',
    ],
}

AUTO_VALUES = {
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

COMPONENT_INPUT_SCHEMAS = {
    'exact_match': [{'name': 'value', 'type': 'match_field'}],
    'not_equals': [{'name': 'value', 'type': 'match_field'}],
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


def get_capability(domain, target_type='project_db'):
    case_types = []
    for ct in CaseType.objects.filter(domain=domain, is_deprecated=False):
        fields = []
        properties = CaseProperty.objects.filter(
            case_type=ct, deprecated=False,
        ).exclude(data_type=CaseProperty.DataType.PASSWORD)

        for prop in properties:
            field_type = DATATYPE_TO_FIELD_TYPE.get(prop.data_type, 'text')
            field = {
                'name': prop.name,
                'type': field_type,
                'operations': OPERATIONS_BY_FIELD_TYPE.get(field_type, []),
            }
            if field_type == 'select':
                field['options'] = list(
                    prop.allowed_values.values_list('allowed_value', flat=True)
                )
            fields.append(field)
        case_types.append({'name': ct.name, 'fields': fields})

    return {
        'case_types': case_types,
        'auto_values': AUTO_VALUES,
        'component_schemas': COMPONENT_INPUT_SCHEMAS,
    }
