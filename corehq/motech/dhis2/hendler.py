from __future__ import absolute_import
from __future__ import unicode_literals

from collections import namedtuple

from dimagi.utils.dates import force_to_datetime

from corehq.apps.users.models import CouchUser
from corehq.motech.dhis2.const import LOCATION_DHIS_ID
from corehq.motech.openmrs.repeater_helpers import get_form_question_values
import logging
import six

logger = logging.getLogger('dhis2')
Dhis2Response = namedtuple('Dhis2Response', 'status_code reason content')


def _get_program(config, form_data=None, payload=None):
    return {'program': config.program_id}


def _get_org_unit(config, form_data=None, payload=None):
    org_unit_id = config.org_unit_id
    if not org_unit_id:
        user_id = payload.get('@user_id')
        user = CouchUser.get_by_user_id(user_id)
        location = user.get_sql_location(payload.get('domain'))
        org_unit_id = location.metadata.get(LOCATION_DHIS_ID, None)

    if not org_unit_id:
        return {}
    return {'orgUnit': org_unit_id}


def _get_event_date(config, form_data=None, payload=None):
    event_date_spec = config.event_date
    event_date = event_date_spec.get_value(form_data)
    if not event_date:
        event_date = payload.get('received_on')
    event_date = force_to_datetime(event_date)
    return {'eventDate': event_date.strftime("%Y-%m-%d")}


def _get_event_status(config, form_data=None, payload=None):
    return {'status': config.event_status}


def _get_datavalues(config, form_data=None, payload=None):
    values = []
    for data_value in config.datavalue_maps:
        values.append(
            {
                'dataElement': data_value.data_element_id,
                'value': data_value.value.get_value(form_data)
            }
        )
    return {'dataValues': values}


def _to_dhis_format(config, payload):
    form_data = get_form_question_values(payload)
    dhis_format = {}

    to_dhis_format = {
        'program_id': _get_program,
        'org_unit_id': _get_org_unit,
        'event_date': _get_event_date,
        'event_status': _get_event_status,
        'datavalue_maps': _get_datavalues,
    }

    for key, func in six.iteritems(to_dhis_format):
        dhis_format.update(func(config, form_data, payload))

    return dhis_format


def send_data_to_dhis2(request, dhis2_config, payload):
    dhis_format = _to_dhis_format(dhis2_config, payload)
    return request.post('/api/26/events', json=dhis_format)
