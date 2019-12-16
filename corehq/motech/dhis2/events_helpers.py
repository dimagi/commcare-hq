from schema import Optional as SchemaOptional, SchemaError
from schema import Regex, Schema

from corehq.motech.dhis2.const import DHIS2_API_VERSION
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.value_source import (
    CaseTriggerInfo,
    get_form_question_values,
    get_value,
)


def send_dhis2_event(request, form_config, payload):
    event = get_event(request.domain_name, form_config, payload)
    validate_event_schema(event)
    return request.post('/api/%s/events' % DHIS2_API_VERSION, json=event,
                        raise_for_status=True)


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
        org_unit_id = get_value(config.org_unit_id, case_trigger_info)
    if org_unit_id:
        return {'orgUnit': org_unit_id}
    return {}


def _get_event_date(config, case_trigger_info):
    event_date = get_value(config.event_date, case_trigger_info)
    return {'eventDate': event_date}


def _get_event_status(config, case_trigger_info):
    return {'status': config.event_status}


def _get_completed_date(config, case_trigger_info):
    completed_date = None
    if config.completed_date:
        completed_date = get_value(config.completed_date, case_trigger_info)
    if completed_date:
        return {'completedDate': completed_date}
    return {}


def _get_datavalues(config, case_trigger_info):
    values = []
    for data_value in config.datavalue_maps:
        values.append({
            'dataElement': data_value.data_element_id,
            'value': get_value(data_value.value, case_trigger_info)
        })
    return {'dataValues': values}


def validate_event_schema(event):
    """
    Raises ConfigurationError if ``event`` is missing required
    properties, or value data types are invalid.
    """
    try:
        Schema(get_event_schema()).validate(event)
    except SchemaError as err:
        raise ConfigurationError from err


def get_event_schema() -> dict:
    """
    Returns the schema for a DHIS2 Event.

    >>> event = {
    ...   "program": "eBAyeGv0exc",
    ...   "orgUnit": "DiszpKrYNg8",
    ...   "eventDate": "2013-05-17",
    ...   "status": "COMPLETED",
    ...   "completedDate": "2013-05-18",
    ...   "storedBy": "admin",
    ...   "coordinate": {
    ...     "latitude": 59.8,
    ...     "longitude": 10.9
    ...   },
    ...   "dataValues": [
    ...     { "dataElement": "qrur9Dvnyt5", "value": "22" },
    ...     { "dataElement": "oZg33kd9taw", "value": "Male" },
    ...     { "dataElement": "msodh3rEMJa", "value": "2013-05-18" }
    ...   ]
    ... }
    >>> Schema(get_event_schema()).is_valid(event)
    True

    """
    date_str = Regex(r"^\d{4}-\d{2}-\d{2}$")
    dhis2_id_str = Regex(r"^[A-Za-z0-9]+$")  # (ASCII \w without underscore)
    return {
        "program": dhis2_id_str,
        "orgUnit": dhis2_id_str,
        "eventDate": date_str,
        SchemaOptional("completedDate"): date_str,
        SchemaOptional("status"): Regex("^(ACTIVE|COMPLETED|VISITED|SCHEDULE|OVERDUE|SKIPPED)$"),
        SchemaOptional("storedBy"): str,
        SchemaOptional("coordinate"): {
            "latitude": float,
            "longitude": float,
        },
        SchemaOptional("geometry"): {
            "type": str,
            "coordinates": [float],
        },
        SchemaOptional("assignedUser"): dhis2_id_str,
        "dataValues": [{
            "dataElement": dhis2_id_str,
            "value": object,
        }],
    }
