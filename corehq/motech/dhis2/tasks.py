from datetime import datetime

from celery.schedules import crontab
from celery.task import periodic_task, task

from toggle.shortcuts import find_domains_with_toggle_enabled

from corehq import toggles
from corehq.motech.dhis2.models import (
    SQLDataSetMap,
    get_dataset,
    should_send_on_date,
)


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
    for dataset_map in SQLDataSetMap.objects.filter(domain=domain_name).all():
        if send_now or should_send_on_date(dataset_map, send_date):
            conn = dataset_map.connection_settings
            dataset = get_dataset(dataset_map, send_date)
            with conn.get_requests() as requests:
                requests.post('/api/dataValueSets', json=dataset)


@periodic_task(
    run_every=crontab(minute=3, hour=3),
    queue='background_queue'
)
def send_datasets_for_all_domains():
    for domain_name in find_domains_with_toggle_enabled(toggles.DHIS2_INTEGRATION):
        send_datasets(domain_name)
