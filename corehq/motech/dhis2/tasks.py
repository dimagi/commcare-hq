import traceback
from datetime import datetime
from psycopg2 import DatabaseError
from django.utils.translation import ugettext_lazy as _
from celery.schedules import crontab
from celery.task import periodic_task, task

from corehq.motech.utils import pformat_json
from toggle.shortcuts import find_domains_with_toggle_enabled

from corehq import toggles
from corehq.motech.dhis2.models import (
    SQLDataSetMap,
    parse_dataset_for_request,
    should_send_on_date,
)
from corehq.util.view_utils import reverse
from corehq.privileges import DATA_FORWARDING
from corehq.apps.domain.models import Domain


@periodic_task(
    run_every=crontab(minute=3, hour=3),
    queue='background_queue'
)
def send_datasets_for_all_domains():
    for domain in find_domains_with_toggle_enabled(toggles.DHIS2_INTEGRATION):
        send_datasets.delay(domain) if _data_forwarding_privilege(domain) else None


@task(serializer='pickle', queue='background_queue')
def send_datasets(domain_name, send_now=False, send_date=None):
    if not send_date:
        send_date = datetime.utcnow().date()
    for dataset_map in SQLDataSetMap.objects.filter(domain=domain_name).all():
        if send_now or should_send_on_date(dataset_map, send_date):
            send_dataset(dataset_map, send_date)


def _data_forwarding_privilege(domain_name):
    return Domain.get_by_name(domain_name).has_privilege(DATA_FORWARDING)


def send_dataset(
    dataset_map: SQLDataSetMap,
    send_date: datetime.date
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
    payload_id = dataset_map.ucr_id  # Allows us to filter Remote API Logs
    response_log_url = reverse(
        'motech_log_list_view',
        args=[dataset_map.domain],
        params={'filter_payload': payload_id}
    )

    with dataset_map.connection_settings.get_requests(payload_id) as requests:
        response = None
        try:
            datavalues_sets = parse_dataset_for_request(dataset_map, send_date)

            for datavalues_set in datavalues_sets:
                response = requests.post('/api/dataValueSets', json=datavalues_set,
                              raise_for_status=True)

        except DatabaseError as db_err:
            requests.notify_error(message=str(db_err),
                                  details=traceback.format_exc())
            return {
                'success': False,
                'error': _('There was an error retrieving some UCR data. '
                           'Try contacting support to help resolve this issue.'),
                'text': None,
                'log_url': response_log_url,
            }

        except Exception as err:
            requests.notify_error(message=str(err),
                                  details=traceback.format_exc())
            text = pformat_json(response.text if response else None)

            return {
                'success': False,
                'error': str(err),
                'status_code': response.status_code if response else None,
                'text': text,
                'log_url': response_log_url,
            }
        else:
            return {
                'success': True,
                'status_code': response.status_code,
                'text': pformat_json(response.text),
                'log_url': response_log_url,
            }
