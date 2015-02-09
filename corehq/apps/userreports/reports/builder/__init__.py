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
    ('username', 'string'),
    ('userID', 'string'),
    ('timeStart', 'datetime'),
    ('timeEnd', 'datetime'),
    ('deviceID', 'string'),
]


def make_case_property_indicator(property_name):
    '''
    Return a data source indicator configuration (a dict) for the given case
    property.
    '''
    return {
        "type": "raw",
        "column_id": property_name,
        "datatype": DEFAULT_CASE_PROPERTY_DATATYPES.get(property_name, "string"),
        'property_name': property_name,
        "display_name": property_name,
    }


def make_form_question_indicator(question):
    '''
    Return a data source indicator configuration (a dict) for the given form
    question.
    '''
    path = question['value'].split('/')
    data_type = question['type']
    options = question.get('options')
    ret = {
        "type": "raw",
        "column_id": path[-1],
        'property_path': ['form'] + path[2:],
        "display_name": path[-1],
    }
    ret.update(_get_form_indicator_data_type(data_type, options))
    return ret


def make_form_meta_block_indicator(field_name, data_type):
    '''
    Return a data source indicator configuration (a dict) for the given
    form meta field and data type.
    '''
    ret = {
        "type": "raw",
        "column_id": field_name,
        "property_path": ['form', 'meta'] + [field_name],
        "display_name": field_name,
    }
    ret.update(_get_form_indicator_data_type(data_type, []))
    return ret


def _get_form_indicator_data_type(data_type, options):
    if data_type == "date":
        return {"datatype": "date"}
    if data_type == "MSelect":
        return {
            "type": "choice_list",
            "select_style": FORM_QUESTION_DATATYPE_MAP[data_type],
            "choices": [
                option['value'] for option in options
            ],
        }
    return {"datatype": "string"}
