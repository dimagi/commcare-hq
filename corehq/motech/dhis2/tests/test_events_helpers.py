import doctest
import json
from datetime import datetime
from unittest.mock import Mock

from django.test.testcases import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.users.models import WebUser
from corehq.motech.dhis2.const import DHIS2_DATA_TYPE_DATE, LOCATION_DHIS_ID
from corehq.motech.dhis2.events_helpers import get_event
from corehq.motech.dhis2.forms import Dhis2ConfigForm
from corehq.motech.dhis2.repeaters import Dhis2Repeater
from corehq.motech.models import ConnectionSettings
from corehq.motech.value_source import CaseTriggerInfo, get_form_question_values

DOMAIN = "dhis2-test"


class TestDhis2EventsHelpers(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(DOMAIN)
        location_type = LocationType.objects.create(
            domain=DOMAIN,
            name='test_location_type',
        )
        cls.location = SQLLocation.objects.create(
            domain=DOMAIN,
            name='test location',
            location_id='test_location',
            location_type=location_type,
            latitude='-33.8655',
            longitude='18.6941',
            metadata={LOCATION_DHIS_ID: "dhis2_location_id"},
        )
        cls.user = WebUser.create(DOMAIN, 'test', 'passwordtest', None, None)
        cls.user.set_location(DOMAIN, cls.location)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain.name, deleted_by=None)
        cls.location.delete()
        cls.domain.delete()
        super().tearDownClass()

    def setUp(self):
        self.form = {
            "domain": DOMAIN,
            "form": {
                "@xmlns": "test_xmlns",
                "event_date": "2017-05-25T21:06:27.012000",
                "completed_date": "2017-05-25T21:06:27.012000",
                "event_location": "-33.6543213 19.12344312 abcdefg",
                "name": "test event",
                "meta": {
                    "location": '',
                    "timeEnd": "2017-05-25T21:06:27.012000",
                    "timeStart": "2017-05-25T21:06:17.739000",
                    "userID": self.user.user_id,
                    "username": self.user.username
                }
            },
            "received_on": "2017-05-26T09:17:23.692083Z",
        }
        self.config = {
            'form_configs': json.dumps([{
                'xmlns': 'test_xmlns',
                'program_id': 'test program',
                'event_status': 'COMPLETED',
                'completed_date': {
                    'doc_type': 'FormQuestion',
                    'form_question': '/data/completed_date',
                    'external_data_type': DHIS2_DATA_TYPE_DATE
                },
                'org_unit_id': {
                    'doc_type': 'FormUserAncestorLocationField',
                    'form_user_ancestor_location_field': LOCATION_DHIS_ID
                },
                'event_location': {
                    'form_question': '/data/event_location'
                },
                'datavalue_maps': [
                    {
                        'data_element_id': 'dhis2_element_id',
                        'value': {
                            'doc_type': 'FormQuestion',
                            'form_question': '/data/name'
                        }
                    }
                ]
            }])
        }
        config_form = Dhis2ConfigForm(data=self.config)
        self.assertTrue(config_form.is_valid())
        data = config_form.cleaned_data
        conn = ConnectionSettings.objects.create(url="http://dummy.com", domain=DOMAIN)
        self.repeater = Dhis2Repeater(domain=DOMAIN, connection_settings_id=conn.id)
        self.repeater.dhis2_config['form_configs'] = data['form_configs']
        self.repeater.save()

    def test_form_processing_with_owner(self):
        info = CaseTriggerInfo(
            domain=DOMAIN,
            case_id=None,
            owner_id='test_location',
            form_question_values=get_form_question_values(self.form),
        )
        event = get_event(DOMAIN, self.repeater.dhis2_config['form_configs'][0], form_json=self.form, info=info)

        self.assertDictEqual(
            {
                'dataValues': [
                    {
                        'dataElement': 'dhis2_element_id',
                        'value': 'test event'
                    }
                ],
                'status': 'COMPLETED',
                'completedDate': '2017-05-25',
                'program': 'test program',
                'eventDate': '2017-05-26',
                'orgUnit': 'dhis2_location_id',
                'coordinate': {
                    'latitude': -33.6543,
                    'longitude': 19.1234
                }
            },
            event
        )


class TestNothingToSend(TestCase):

    def setUp(self):
        self.conn = ConnectionSettings.objects.create(
            domain=DOMAIN,
            name='Example DHIS2 server',
            url='https://dhis2.example.com/',
        )

    def tearDown(self):
        self.conn.delete()

    def test_204_response(self):
        form_xmlns = 'http://example.com/test-xmlns'
        dhis2_config = {
            'form_configs': [{
                'xmlns': form_xmlns,
                'program_id': 'abc123',
                'program_stage_id': '',
                'org_unit_id': '',
                'event_date': {'form_question': '/data/event_date'},
                'event_status': {'form_question': '/data/event_status'},
                'completed_date': '',
                'datavalue_maps': [],
                'event_location': '',
            }]
        }
        repeater = Dhis2Repeater(
            domain=DOMAIN,
            connection_settings_id=self.conn.id,
            dhis2_config=dhis2_config,
            dhis2_version='2.39.1.1',
            dhis2_version_last_modified=datetime.utcnow(),
        )
        repeat_record = Mock(payload_id='abc123')
        payload = {'form': {'@xmlns': form_xmlns}}

        result = repeater.send_request(repeat_record, payload)
        self.assertEqual(result.status_code, 204)
        self.assertEqual(result.reason, 'No content')


def test_doctests():
    from corehq.motech.dhis2 import events_helpers

    results = doctest.testmod(events_helpers)
    assert results.failed == 0
