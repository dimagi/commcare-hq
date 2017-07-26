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


def make_case_data_source_filter(case_type):
    return {
        "type": "boolean_expression",
        "operator": "eq",
        "expression": {
            "type": "property_name",
            "property_name": "type"
        },
        "property_value": case_type,
    }


def make_form_data_source_filter(xmlns):
    return {
        "type": "boolean_expression",
        "operator": "eq",
        "expression": {
            "type": "property_name",
            "property_name": "xmlns"
        },
        "property_value": xmlns,
    }


def make_case_property_indicator(property_name, column_id=None, datatype=None):
    """
    Return a data source indicator configuration (a dict) for the given case
    property.
    """
    datatype = datatype or DEFAULT_CASE_PROPERTY_DATATYPES.get(property_name, "string")

    return {
        "type": "expression",
        "column_id": column_id or property_name,
        "datatype": datatype,
        "display_name": property_name,
        "expression": {
            "type": "property_name",
            "property_name": property_name,
        },
    }


def _make_user_group_or_location_indicator(property_name, column_id):
    """
    Return a data source indicator config with the given column_id that stores
    a user name, group name, or location name for the id corresponding to the
    given property_name.
    """
    return {
        "datatype": "string",
        "type": "expression",
        "column_id": column_id,
        "expression": {
            "test": {
                "operator": "eq",
                "expression": {
                    "value_expression": {
                        "type": "property_name",
                        "property_name": "doc_type"
                    },
                    "type": "related_doc",
                    "related_doc_type": "Group",
                    "doc_id_expression": {
                        "type": "property_name",
                        "property_name": property_name
                    }
                },
                "type": "boolean_expression",
                "property_value": "Group"
            },
            "expression_if_true": {
                "value_expression": {
                    "type": "property_name",
                    "property_name": "name"
                },
                "type": "related_doc",
                "related_doc_type": "Group",
                "doc_id_expression": {
                    "type": "property_name",
                    "property_name": property_name
                }
            },
            "type": "conditional",
            "expression_if_false": {
                "type": "conditional",
                "test": {
                    "operator": "eq",
                    "expression": {
                        "value_expression": {
                            "type": "property_name",
                            "property_name": "doc_type"
                        },
                        "type": "related_doc",
                        "related_doc_type": "CommCareUser",
                        "doc_id_expression": {
                            "type": "property_name",
                            "property_name": property_name
                        }
                    },
                    "type": "boolean_expression",
                    "property_value": "CommCareUser"
                },
                "expression_if_true": {
                    "value_expression": {
                        "type": "property_name",
                        "property_name": "username"
                    },
                    "type": "related_doc",
                    "related_doc_type": "CommCareUser",
                    "doc_id_expression": {
                        "type": "property_name",
                        "property_name": property_name
                    }
                },
                "expression_if_false": {
                    "value_expression": {
                        "type": "property_name",
                        "property_name": "name"
                    },
                    "type": "related_doc",
                    "related_doc_type": "Location",
                    "doc_id_expression": {
                        "type": "property_name",
                        "property_name": property_name
                    }
                }
            }
        }
    }


def make_user_name_indicator(column_id):
    return _make_user_group_or_location_indicator("user_id", column_id)


def make_owner_name_indicator(column_id):
    return _make_user_group_or_location_indicator("owner_id", column_id)


def make_form_question_indicator(question, column_id=None, data_type=None, root_doc=False):
    """
    Return a data source indicator configuration (a dict) for the given form
    question.
    """
    path = question['value'].split('/')
    expression = {
        "type": "property_path",
        'property_path': ['form'] + path[2:],
    }
    if root_doc:
        expression = {"type": "root_doc", "expression": expression}
    return {
        "type": "expression",
        "column_id": column_id or question['value'],
        "display_name": path[-1],
        "datatype": data_type or get_form_indicator_data_type(question['type']),
        "expression": expression
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


def make_form_meta_block_indicator(spec, column_id=None, root_doc=False):
    """
    Return a data source indicator configuration (a dict) for the given
    form meta field and data type.
    """
    field_name = spec[0]
    if isinstance(field_name, basestring):
        field_name = [field_name]
    data_type = spec[1]
    column_id = column_id or field_name[0]
    expression = {
        "type": "property_path",
        "property_path": ['form', 'meta'] + field_name,
    }
    if root_doc:
        expression = {"type": "root_doc", "expression": expression}
    return {
        "type": "expression",
        "column_id": column_id,
        "display_name": field_name[0],
        "datatype": get_form_indicator_data_type(data_type),
        "expression": expression
    }


def get_form_indicator_data_type(question_type):
    return {
        "date": "date",
        "datetime": "datetime",
        "Date": "date",
        "DateTime": "datetime",
        "Int": "integer",
        "Double": "decimal",
        "Text": "string",
        "string": "string",
    }.get(question_type, "string")


def get_filter_format_from_question_type(question_type):
    return {
        "Date": 'date',
        "DateTime": "date",
        "Text": "dynamic_choice_list",
        "Int": "numeric",
        "Double": "numeric",
    }.get(question_type, "dynamic_choice_list")
