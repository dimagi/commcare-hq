from dimagi.utils.dates import force_to_datetime

from corehq.apps.users.models import CouchUser
from corehq.motech.dhis2.const import DHIS2_API_VERSION, LOCATION_DHIS_ID
from corehq.motech.value_source import (
    CaseTriggerInfo,
    get_form_question_values,
    get_owner_location, get_ancestor_location_metadata_value)


def send_dhis2_event(request, form_config, payload):
    event = get_event(request.domain_name, form_config, payload)
    return request.post('/api/%s/events' % DHIS2_API_VERSION, json=event)


def get_event(domain, config, form_json):
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
        form_question_values=get_form_question_values(form_json),
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
        event.update(func(config, info, form_json))
    return event


def _get_program(config, case_trigger_info, form_json):
    return {'program': config.program_id}


def _get_org_unit(config, case_trigger_info, form_json):
    org_unit_id = None
    if config.org_unit_id:
        org_unit_id = config.org_unit_id.get_value(case_trigger_info)
    if not org_unit_id:
        # Fall back to location metadata of submitter's location
        user_id = case_trigger_info.form_question_values.get("/metadata/userID")
        if user_id:
            location = get_owner_location(case_trigger_info.domain, user_id)
            org_unit_id = get_ancestor_location_metadata_value(location, LOCATION_DHIS_ID)
    if org_unit_id:
        return {'orgUnit': org_unit_id}
    return {}


def _get_event_date(config, case_trigger_info, form_json):
    event_date = None
    if config.event_date:
        event_date = config.event_date.get_value(case_trigger_info)
    if not event_date:
        # Fall back to form meta "received_on"
        event_date = case_trigger_info.form_question_values.get("/metadata/received_on")
    event_date = force_to_datetime(event_date)
    return {'eventDate': event_date.strftime("%Y-%m-%d")}


def _get_event_status(config, case_trigger_info, form_json):
    return {'status': config.event_status}


def _get_datavalues(config, case_trigger_info, form_json):
    values = []
    for data_value in config.datavalue_maps:
        values.append({
            'dataElement': data_value.data_element_id,
            'value': data_value.value.get_value(case_trigger_info)
        })
    return {'dataValues': values}
