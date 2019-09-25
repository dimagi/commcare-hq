import logging
from collections import namedtuple

from dimagi.utils.dates import force_to_datetime

from corehq.apps.users.models import CouchUser
from corehq.motech.dhis2.const import DHIS2_API_VERSION, LOCATION_DHIS_ID
from corehq.motech.value_source import (
    CaseTriggerInfo,
    get_form_question_values,
)

logger = logging.getLogger('dhis2')
Dhis2Response = namedtuple('Dhis2Response', 'status_code reason content')


def _get_program(config, case_trigger_info=None, payload=None):
    return {'program': config.program_id}


def _get_org_unit(config, case_trigger_info=None, payload=None):
    org_unit_id_spec = config.org_unit_id
    org_unit_id = org_unit_id_spec.get_value(case_trigger_info) if org_unit_id_spec else None
    if not org_unit_id:
        user_id = payload.get('@user_id')
        user = CouchUser.get_by_user_id(user_id)
        location = user.get_sql_location(payload.get('domain'))
        org_unit_id = location.metadata.get(LOCATION_DHIS_ID, None)

    if not org_unit_id:
        return {}
    return {'orgUnit': org_unit_id}


def _get_event_date(config, case_trigger_info=None, payload=None):
    event_date_spec = config.event_date
    event_date = event_date_spec.get_value(case_trigger_info)
    if not event_date:
        event_date = payload.get('received_on')
    event_date = force_to_datetime(event_date)
    return {'eventDate': event_date.strftime("%Y-%m-%d")}


def _get_event_status(config, case_trigger_info=None, payload=None):
    return {'status': config.event_status}


def _get_datavalues(config, case_trigger_info=None, payload=None):
    values = []
    for data_value in config.datavalue_maps:
        values.append(
            {
                'dataElement': data_value.data_element_id,
                'value': data_value.value.get_value(case_trigger_info)
            }
        )
    return {'dataValues': values}


def _to_dhis_format(config, payload):
    info = CaseTriggerInfo(None, None, None, None, None, form_question_values=get_form_question_values(payload))
    dhis_format = {}

    to_dhis_format_functions = [
        _get_program,
        _get_org_unit,
        _get_event_date,
        _get_event_status,
        _get_datavalues,
    ]

    for func in to_dhis_format_functions:
        dhis_format.update(func(config, info, payload))

    return dhis_format


def send_dhis2_event(request, dhis2_config, payload):
    dhis_format = _to_dhis_format(dhis2_config, payload)
    return request.post('/api/%s/events' % DHIS2_API_VERSION, json=dhis_format)
