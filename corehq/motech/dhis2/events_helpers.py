from corehq.motech.dhis2.const import DHIS2_API_VERSION
from corehq.motech.value_source import (
    CaseTriggerInfo,
    get_form_question_values,
)


def send_dhis2_event(request, form_config, payload):
    event = get_event(request.domain_name, form_config, payload)
    event = event_schema.validate(event)
    return request.post('/api/%s/events' % DHIS2_API_VERSION, json=event)


def get_event(domain, config, form_json):
    info = CaseTriggerInfo(
        domain=domain,
        case_id=None,
        form_question_values=get_form_question_values(form_json),
    )
    event = {}
    event_property_functions = [
        _get_program,
        _get_org_unit,
        _get_event_date,
        _get_event_status,
        _get_completed_date,
        _get_datavalues,
    ]
    for func in event_property_functions:
        event.update(func(config, info))
    return event


def _get_program(config, case_trigger_info):
    return {'program': config.program_id}


def _get_org_unit(config, case_trigger_info):
    org_unit_id = None
    if config.org_unit_id:
        org_unit_id = config.org_unit_id.get_value(case_trigger_info)
    if org_unit_id:
        return {'orgUnit': org_unit_id}
    return {}


def _get_event_date(config, case_trigger_info):
    event_date = config.event_date.get_value(case_trigger_info)
    return {'eventDate': event_date}


def _get_event_status(config, case_trigger_info):
    return {'status': config.event_status}


def _get_completed_date(config, case_trigger_info):
    completed_date = None
    if config.completed_date:
        completed_date = config.completed_date.get_value(case_trigger_info)
    if completed_date:
        return {'completedDate': completed_date}
    return {}


def _get_datavalues(config, case_trigger_info):
    values = []
    for data_value in config.datavalue_maps:
        values.append({
            'dataElement': data_value.data_element_id,
            'value': data_value.value.get_value(case_trigger_info)
        })
    return {'dataValues': values}
