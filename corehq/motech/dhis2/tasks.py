from datetime import datetime

from celery.schedules import crontab
from celery.task import periodic_task, task

from toggle.shortcuts import find_domains_with_toggle_enabled

from corehq import toggles
from corehq.motech.dhis2.dbaccessors import get_dataset_maps
from corehq.motech.dhis2.models import Dhis2Connection
from corehq.motech.requests import Requests


@task(serializer='pickle', queue='background_queue')
def send_datasets(domain_name, send_now=False, send_date=None):
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
    if not send_date:
        send_date = datetime.today()
    dhis2_conn = Dhis2Connection.objects.filter(domain=domain_name).first()
    dataset_maps = get_dataset_maps(domain_name)
    if not dataset_maps:
        return  # Nothing to do
    for dataset_map in dataset_maps:
        if send_now or dataset_map.should_send_on_date(send_date):
            if dataset_map.connection_settings:
                conn = dataset_map.connection_settings
                url = conn.url
                endpoint = '/api/dataValueSets'
            else:
                conn = dhis2_conn
                url = conn.server_url
                endpoint = 'dataValueSets'
            if not conn:
                continue

            dataset = dataset_map.get_dataset(send_date)
            requests = Requests(
                domain_name,
                url,
                conn.username,
                conn.plaintext_password,
                verify=not conn.skip_cert_verify,
                notify_addresses=conn.notify_addresses if hasattr(conn, 'notify_addresses') else None
            )
            requests.post(endpoint, json=dataset)


@periodic_task(
    run_every=crontab(minute=3, hour=3),
    queue='background_queue'
)
def send_datasets_for_all_domains():
    for domain_name in find_domains_with_toggle_enabled(toggles.DHIS2_INTEGRATION):
        send_datasets(domain_name)
