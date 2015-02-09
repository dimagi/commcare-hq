DEFAULT_CASE_PROPERTY_DATATYPES = {
    "name": "string",
    "modified_on": "datetime",
    "opened_on": "datetime",
    "owner_id": "string",
    "user_id": "string",
}


def make_case_property_indicator(property_name):
    '''
    Return a data source indicator configuration (a dict) for the given case
    property.
    :param property_name:
    :return:
    '''
    return {
        "type": "raw",
        "column_id": property_name,
        "datatype": DEFAULT_CASE_PROPERTY_DATATYPES.get(property_name, "string"),
        'property_name': property_name,
        "display_name": property_name,
    }
