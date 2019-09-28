from dimagi.utils.dates import force_to_datetime

from corehq.apps.users.models import CouchUser
from corehq.motech.dhis2.const import DHIS2_API_VERSION, LOCATION_DHIS_ID
from corehq.motech.value_source import (
    CaseTriggerInfo,
    get_form_question_values,
)


def send_dhis2_event(request, form_config, payload):
    event = get_event(request.domain_name, form_config, payload)
    return request.post('/api/%s/events' % DHIS2_API_VERSION, json=event)


def get_event(domain, config, payload):
    info = CaseTriggerInfo(
        domain=domain,
        case_id=None,
        type=None,
        name=None,
        owner_id=None,
        modified_by=None,
        updates=None,
        created=None,
        closed=None,
        extra_fields=None,
        form_question_values=get_form_question_values(payload),
    )
    event = {}
    event_property_functions = [
        _get_program,
        _get_org_unit,
        _get_event_date,
        _get_event_status,
        _get_datavalues,
    ]
    for func in event_property_functions:
        event.update(func(config, info, payload))
    return event


def _get_program(config, case_trigger_info, payload):
    return {'program': config.program_id}


def _get_org_unit(config, case_trigger_info, payload):
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


def _get_event_date(config, case_trigger_info, payload):
    event_date_spec = config.event_date
    event_date = event_date_spec.get_value(case_trigger_info)
    if not event_date:
        event_date = payload.get('received_on')
    event_date = force_to_datetime(event_date)
    return {'eventDate': event_date.strftime("%Y-%m-%d")}


def _get_event_status(config, case_trigger_info, payload):
    return {'status': config.event_status}


def _get_datavalues(config, case_trigger_info, payload):
    values = []
    for data_value in config.datavalue_maps:
        values.append({
            'dataElement': data_value.data_element_id,
            'value': data_value.value.get_value(case_trigger_info)
        })
    return {'dataValues': values}
