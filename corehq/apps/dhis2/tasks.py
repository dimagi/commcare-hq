from corehq.apps.dhis2.dbaccessors import get_dhis2_connection, get_dataset_maps
from corehq.apps.dhis2.models import JsonApiRequest


def iter_ucr_data(report_id):
    """
    Generates rows as dictionaries, given a UCR ID. The dictionary expects to have the following format:

    {
        "org_unit_id": "ABC",
        "data_element_cat_option_combo_1": 123,
        "data_element_cat_option_combo_2": 456,
        "data_element_cat_option_combo_3": 789,
    }

    """
    yield


def send_datavalues(domain_name):
    """
    Sends a data set of data values in the following format:

    {
      "dataSet": "dataSetID",
      "completeDate": "date",
      "period": "period",
      "orgUnit": "orgUnitID",
      "attributeOptionCombo", "aocID",
      "dataValues": [
        { "dataElement": "dataElementID", "categoryOptionCombo": "cocID", "value": "1", "comment": "comment1" },
        { "dataElement": "dataElementID", "categoryOptionCombo": "cocID", "value": "2", "comment": "comment2" },
        { "dataElement": "dataElementID", "categoryOptionCombo": "cocID", "value": "3", "comment": "comment3" }
      ]
    }

    See DHIS2 API docs for more details: https://docs.dhis2.org/master/en/developer/html/webapi_data_values.html

    """
    dhis2_conn = get_dhis2_connection(domain_name)
    dataset_maps = get_dataset_maps(domain_name)
    if not dhis2_conn or not dataset_maps:
        return  # Nothing to do
    api = JsonApiRequest(
        dhis2_conn.server_url,
        dhis2_conn.username,
        dhis2_conn.password,
    )
    for dataset_map in dataset_maps:
        # TODO: Refactor into class Dhis2Request(JsonApiRequest).postDataSet(report_data, dataset_map)
        api.post('dataValueSets', dataset_map.get_dataset)
