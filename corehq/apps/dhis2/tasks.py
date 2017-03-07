from datetime import datetime

from celery.schedules import crontab
from celery.task import periodic_task

from corehq import toggles
from corehq.apps.dhis2.dbaccessors import get_dhis2_connection, get_dataset_maps
from corehq.apps.dhis2.models import JsonApiRequest
from corehq.apps.domain.models import Domain


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
        if dataset_map.day_to_send == datetime.today().day:
            api.post('dataValueSets', dataset_map.get_dataset())


@periodic_task(
    run_every=crontab(minute=3, hour=3),
    queue='background_queue'
)
def send_datasets_for_all_domains():
    for row in Domain.get_all(include_docs=False):
        domain_name = row['key']
        if toggles.DHIS2_INTEGRATION.enabled(domain_name):
            send_datavalues(domain_name)
