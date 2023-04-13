from schema import Schema, SchemaError

from corehq.motech.dhis2.schema import get_event_schema
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.repeater_helpers import RepeaterResponse
from corehq.motech.value_source import (
    CaseTriggerInfo,
    get_form_question_values,
    get_value,
)


def send_dhis2_event(request, form_config, payload):
    event = get_event(request.domain_name, form_config, payload)
    if event:
        validate_event_schema(event)
        return request.post('/api/events', json=event, raise_for_status=True)
    else:
        return RepeaterResponse(204, "No content")


def get_event(domain, config, form_json=None, info=None):
    if info is None:
        info = CaseTriggerInfo(
            domain=domain,
            case_id=None,
            form_question_values=get_form_question_values(form_json),
        )
    event = {}
    event_property_functions = [
        _get_program,
        _get_program_stage,
        _get_org_unit,
        _get_event_date,
        _get_event_status,
        _get_completed_date,
        _get_datavalues,
        _get_coordinate,
    ]
    for func in event_property_functions:
        event.update(func(config, info))
    if event['eventDate'] or event['dataValues']:
        # eventDate is a required field, but we return the event if it
        # has no date if it does have values, so that it will fail
        # validation and the administrator will be notified that the
        # value source for eventDate is broken.
        return event
    else:
        # The event has no date and no values. That is not an event.
        return {}


def _get_program(config, case_trigger_info):
    return {'program': config['program_id']}


def _get_program_stage(config, case_trigger_info):
    program_stage_id = None
    if config['program_stage_id']:
        program_stage_id = get_value(config['program_stage_id'], case_trigger_info)
    if program_stage_id:
        return {'programStage': program_stage_id}
    return {}


def _get_org_unit(config, case_trigger_info):
    org_unit_id = None
    if config['org_unit_id']:
        org_unit_id = get_value(config['org_unit_id'], case_trigger_info)
    if org_unit_id:
        return {'orgUnit': org_unit_id}
    return {}


def _get_event_date(config, case_trigger_info):
    event_date = get_value(config['event_date'], case_trigger_info)
    return {'eventDate': event_date}


def _get_event_status(config, case_trigger_info):
    event_status = get_value(config['event_status'], case_trigger_info)
    return {'status': event_status}


def _get_completed_date(config, case_trigger_info):
    completed_date = None
    if config['completed_date']:
        completed_date = get_value(config['completed_date'], case_trigger_info)
    if completed_date:
        return {'completedDate': completed_date}
    return {}


def _get_datavalues(config, case_trigger_info):
    values = []
    for data_value in config['datavalue_maps']:
        value = get_value(data_value['value'], case_trigger_info)
        if value is not None:
            values.append({
                'dataElement': data_value['data_element_id'],
                'value': value
            })
    return {'dataValues': values}


def _get_coordinate(config, case_trigger_info):
    if config['event_location']:
        location_string = get_value(config['event_location'], case_trigger_info)

        if location_string:
            (lat, lon) = _dhis2_geolocation(location_string)
            return {
                'coordinate': {
                    'latitude': lat,
                    'longitude': lon
                }
            }
    return {}


def _dhis2_geolocation(location_string):
    """
    >>> _dhis2_geolocation('-33.6543213 19.12344312 abcdefg')
    (-33.6543, 19.1234)
    """
    (lat, lon) = location_string.split(' ')[:2]
    return round(float(lat), 4), round(float(lon), 4)


def validate_event_schema(event):
    """
    Raises ConfigurationError if ``event`` is missing required
    properties, or value data types are invalid.
    """
    try:
        Schema(get_event_schema()).validate(event)
    except SchemaError as err:
        raise ConfigurationError from err
