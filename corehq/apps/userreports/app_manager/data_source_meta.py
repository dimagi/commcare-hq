DATA_SOURCE_TYPE_CASE = 'case'
DATA_SOURCE_TYPE_FORM = 'form'
DATA_SOURCE_TYPE_RAW = 'data_source'  # this is only used in report builder
APP_DATA_SOURCE_TYPE_VALUES = (DATA_SOURCE_TYPE_CASE, DATA_SOURCE_TYPE_FORM)
REPORT_BUILDER_DATA_SOURCE_TYPE_VALUES = (DATA_SOURCE_TYPE_CASE, DATA_SOURCE_TYPE_FORM, DATA_SOURCE_TYPE_RAW)


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


def make_form_data_source_filter(xmlns, app_id):
    return {
        "type": "and",
        "filters": [
            {
                "type": "boolean_expression",
                "operator": "eq",
                "expression": {
                    "type": "property_name",
                    "property_name": "xmlns"
                },
                "property_value": xmlns,
            },
            {
                "type": "boolean_expression",
                "operator": "eq",
                "expression": {
                    "type": "property_name",
                    "property_name": "app_id"
                },
                "property_value": app_id,
            }
        ]
    }


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


def make_form_meta_block_indicator(spec, column_id=None, root_doc=False):
    """
    Return a data source indicator configuration (a dict) for the given
    form meta field and data type.
    """
    field_name = spec[0]
    if isinstance(field_name, str):
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
