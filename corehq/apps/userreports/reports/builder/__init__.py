
DEFAULT_CASE_PROPERTY_DATATYPES = {
    "name": "string",
    "modified_on": "datetime",
    "opened_on": "datetime",
    "owner_id": "string",
    "user_id": "string",
}

FORM_QUESTION_DATATYPE_MAP = {
    "Select": "single",
    "MSelect": "multiple"
}

FORM_METADATA_PROPERTIES = [
    ('username', 'Text'),
    ('userID', 'Text'),
    ('timeStart', 'DateTime'),
    ('timeEnd', 'DateTime'),
    ('deviceID', 'Text'),
]


def make_case_property_indicator(property_name, column_id=None, datatype=None):
    """
    Return a data source indicator configuration (a dict) for the given case
    property.  This will expand index case references if provided in the format
    parent/host/foo
    """
    datatype = datatype or DEFAULT_CASE_PROPERTY_DATATYPES.get(property_name, "string")

    parts = property_name.split('/')
    root_field = parts.pop()

    expression = {
        'type': 'property_name',
        'property_name': root_field,
    }
    if parts:
        case_expression = {
            'type': 'identity',
        }
        for index in parts:
            case_expression = {
                'type': 'indexed_case',
                'case_expression': case_expression,
                'index': index
            }

        expression = {
            'type': 'nested',
            'argument_expression': case_expression,
            'value_expression': expression
        }

    return {
        "type": "expression",
        "column_id": column_id or property_name,
        "datatype": datatype,
        "display_name": property_name,
        "expression": expression,
    }


def make_multiselect_question_indicator(question, column_id=None):
    path = question['value'].split('/')
    return {
        "type": "choice_list",
        "column_id": column_id or question['value'],
        "display_name": path[-1],
        "property_path": ['form'] + path[2:],
        "select_style": "multiple",
        "choices": [o['value'] for o in question['options']],
    }


def get_filter_format_from_question_type(question_type):
    return {
        "Date": 'date',
        "DateTime": "date",
        "Text": "dynamic_choice_list",
        "Int": "numeric",
        "Double": "numeric",
    }.get(question_type, "dynamic_choice_list")
