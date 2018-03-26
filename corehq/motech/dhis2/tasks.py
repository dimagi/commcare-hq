from __future__ import absolute_import
from __future__ import unicode_literals
from base64 import b64decode
import bz2
from datetime import datetime
import logging

from celery.schedules import crontab
from celery.task import periodic_task, task

from corehq import toggles
from corehq.motech.dhis2.dbaccessors import get_dhis2_connection, get_dataset_maps
from corehq.motech.dhis2.api import JsonApiRequest
from corehq.motech.dhis2.models import JsonApiLog
from toggle.shortcuts import find_domains_with_toggle_enabled


@task(queue='background_queue')
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
    dhis2_conn = get_dhis2_connection(domain_name)
    dataset_maps = get_dataset_maps(domain_name)
    if not dhis2_conn or not dataset_maps:
        return  # Nothing to do
    api = JsonApiRequest(
        domain_name,
        dhis2_conn.server_url,
        dhis2_conn.username,
        bz2.decompress(b64decode(dhis2_conn.password)),
    )
    endpoint = 'dataValueSets'
    for dataset_map in dataset_maps:
        if send_now or dataset_map.should_send_on_date(send_date):
            domain_log_level = getattr(dhis2_conn, 'log_level', logging.INFO)
            try:
                dataset = dataset_map.get_dataset(send_date)
                response = api.post(endpoint, dataset)
            except Exception as err:
                log_level = logging.ERROR
                if log_level >= domain_log_level:
                    JsonApiLog.log(
                        log_level,
                        api,
                        str(err),
                        response_status=None,
                        response_body=None,
                        method_func=api.post,
                        request_url=api.get_request_url(endpoint),
                    )
            else:
                log_level = logging.INFO
                if log_level >= domain_log_level:
                    JsonApiLog.log(
                        log_level,
                        api,
                        None,
                        response_status=response.status_code,
                        response_body=response.content,
                        method_func=api.post,
                        request_url=api.get_request_url(endpoint),
                    )


@periodic_task(
    run_every=crontab(minute=3, hour=3),
    queue='background_queue'
)
def send_datasets_for_all_domains():
    for domain_name in find_domains_with_toggle_enabled(toggles.DHIS2_INTEGRATION):
        send_datasets(domain_name)
