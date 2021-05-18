import traceback
from datetime import datetime
from psycopg2 import DatabaseError
from django.utils.translation import ugettext_lazy as _
from celery.schedules import crontab
from celery.task import periodic_task, task

from toggle.shortcuts import find_domains_with_toggle_enabled

from corehq import toggles
from corehq.motech.dhis2.models import (
    SQLDataSetMap,
    get_dataset,
    should_send_on_date,
)


@periodic_task(
    run_every=crontab(minute=3, hour=3),
    queue='background_queue'
)
def send_datasets_for_all_domains():
    for domain in find_domains_with_toggle_enabled(toggles.DHIS2_INTEGRATION):
        send_datasets.delay(domain)


@task(serializer='pickle', queue='background_queue')
def send_datasets(domain_name, send_now=False, send_date=None):
    if not send_date:
        send_date = datetime.utcnow().date()
    for dataset_map in SQLDataSetMap.objects.filter(domain=domain_name).all():
        if send_now or should_send_on_date(dataset_map, send_date):
            send_dataset(dataset_map, send_date)


def send_dataset(
    dataset_map: SQLDataSetMap,
    send_date: datetime.date,
) -> dict:
    """
    Sends a data set of data values in the following format. "period" is
    determined from ``send_date``. ::

        {
            "dataSet": "dataSetID",
            "completeDate": "date",
            "period": "period",
            "orgUnit": "orgUnitID",
            "attributeOptionCombo", "aocID",
            "dataValues": [
                {
                    "dataElement": "dataElementID",
                    "categoryOptionCombo": "cocID",
                    "value": "1",
                    "comment": "comment1"
                },
                {
                    "dataElement": "dataElementID",
                    "categoryOptionCombo": "cocID",
                    "value": "2",
                    "comment": "comment2"
                },
                {
                    "dataElement": "dataElementID",
                    "categoryOptionCombo": "cocID",
                    "value": "3",
                    "comment": "comment3"
                }
            ]
        }

    See `DHIS2 API docs`_ for more details.


    .. _DHIS2 API docs: https://docs.dhis2.org/master/en/developer/html/webapi_data_values.html

    """
    with dataset_map.connection_settings.get_requests() as requests:
        response = None
        try:
            dataset = get_dataset(dataset_map, send_date)
            response = requests.post('/api/dataValueSets', json=dataset,
                                     raise_for_status=True)
        except DatabaseError:
            return {
                'success': False,
                'error': _('There was an error retrieving some UCR data. '
                           'Try contacting support to help resolve this issue.'),
                'traceback': traceback.format_exc(),
            }
        except Exception as err:
            requests.notify_error(message=str(err),
                                  details=traceback.format_exc())
            return {
                'success': False,
                'error': str(err),
                'traceback': traceback.format_exc(),
                'status_code': response.status_code if response else None,
                'text': response.text if response else None,
            }
        else:
            return {
                'success': True,
                'status_code': response.status_code,
                'text': response.text,
            }
