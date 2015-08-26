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


def make_case_property_indicator(property_name, column_id=None):
    """
    Return a data source indicator configuration (a dict) for the given case
    property.
    """
    return {
        "type": "raw",
        "column_id": column_id or property_name,
        "datatype": DEFAULT_CASE_PROPERTY_DATATYPES.get(property_name, "string"),
        'property_name': property_name,
        "display_name": property_name,
    }


def make_owner_name_indicator(column_id):
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
                        "property_name": "owner_id"
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
                    "property_name": "owner_id"
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
                            "property_name": "owner_id"
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
                        "property_name": "owner_id"
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
                        "property_name": "owner_id"
                    }
                }
            }
        }
    }


def make_form_question_indicator(question, column_id=None):
    """
    Return a data source indicator configuration (a dict) for the given form
    question.
    """
    path = question['value'].split('/')
    data_type = question['type']
    ret = {
        "type": "raw",
        "column_id": column_id or question['value'],
        'property_path': ['form'] + path[2:],
        "display_name": path[-1],
    }
    ret.update(_get_form_indicator_data_type(data_type))
    return ret


def make_form_meta_block_indicator(spec, column_id=None):
    """
    Return a data source indicator configuration (a dict) for the given
    form meta field and data type.
    """
    field_name = spec[0]
    data_type = spec[1]
    column_id = column_id or field_name
    ret = {
        "type": "raw",
        "column_id": column_id,
        "property_path": ['form', 'meta'] + [field_name],
        "display_name": field_name,
    }
    ret.update(_get_form_indicator_data_type(data_type))
    return ret


def _get_form_indicator_data_type(data_type):
    if data_type in ["date", "datetime"]:
        return {"datatype": data_type}
    return {"datatype": "string"}
