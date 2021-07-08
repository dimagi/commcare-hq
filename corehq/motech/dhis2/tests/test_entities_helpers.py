import doctest
import json

from django.test import SimpleTestCase
from django.test.testcases import TestCase

from corehq.motech.dhis2.entities_helpers import validate_tracked_entity
from corehq.motech.exceptions import ConfigurationError

from fakecouch import FakeCouchDb

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.users.models import WebUser
from corehq.motech.dhis2.const import DHIS2_DATA_TYPE_DATE, LOCATION_DHIS_ID
from corehq.motech.dhis2.dhis2_config import Dhis2FormConfig
from corehq.motech.dhis2.forms import Dhis2ConfigForm
from corehq.motech.dhis2.repeaters import Dhis2Repeater
from corehq.motech.dhis2.entities_helpers import get_programs_by_id
from corehq.motech.value_source import CaseTriggerInfo, get_form_question_values

DOMAIN = "dhis2-test"


class ValidateTrackedEntityTests(SimpleTestCase):

    def test_valid(self):
        """
        validate_tracked_entity() should not raise ConfigurationError
        """
        tracked_entity = {
            "orgUnit": "abc123",
            "trackedEntityType": "def456",
        }
        validate_tracked_entity(tracked_entity)

    def test_extra_key(self):
        tracked_entity = {
            "orgUnit": "abc123",
            "trackedEntityType": "def456",
            "hasWensleydale": False
        }
        with self.assertRaises(ConfigurationError):
            validate_tracked_entity(tracked_entity)

    def test_missing_key(self):
        tracked_entity = {
            "trackedEntityType": "def456",
        }
        with self.assertRaises(ConfigurationError):
            validate_tracked_entity(tracked_entity)

    def test_bad_data_type(self):
        tracked_entity = {
            "orgUnit": 0xabc123,
            "trackedEntityType": 0xdef456
        }
        with self.assertRaises(ConfigurationError):
            validate_tracked_entity(tracked_entity)


class TestDhis2EntitiesHelpers(TestCase):

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
            latitude='-33.6543',
            longitude='19.1234',
            metadata={LOCATION_DHIS_ID: "dhis2_location_id"},
        )
        cls.user = WebUser.create(DOMAIN, 'test', 'passwordtest', None, None)
        cls.user.set_location(DOMAIN, cls.location)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(deleted_by=None)
        cls.location.delete()
        cls.domain.delete()
        super().tearDownClass()

    def setUp(self):
        self.db = Dhis2Repeater.get_db()
        self.fakedb = FakeCouchDb()
        Dhis2Repeater.set_db(self.fakedb)

    def tearDown(self):
        Dhis2Repeater.set_db(self.db)

    def test_get_programs_by_id(self):
        program_id = 'test program'

        form = {
            "domain": DOMAIN,
            "form": {
                "@xmlns": "test_xmlns",
                "event_date": "2017-05-25T21:06:27.012000",
                "completed_date": "2017-05-25T21:06:27.012000",
                "name": "test event",
                "meta": {
                    "location": 'test location',
                    "timeEnd": "2017-05-25T21:06:27.012000",
                    "timeStart": "2017-05-25T21:06:17.739000",
                    "userID": self.user.user_id,
                    "username": self.user.username
                }
            },
            "received_on": "2017-05-26T09:17:23.692083Z",
        }
        config = {
            'form_configs': json.dumps([{
                'xmlns': 'test_xmlns',
                'program_id': program_id,
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
        config_form = Dhis2ConfigForm(data=config)
        self.assertTrue(config_form.is_valid())
        data = config_form.cleaned_data
        repeater = Dhis2Repeater()
        repeater.dhis2_config.form_configs = [Dhis2FormConfig.wrap(fc) for fc in data['form_configs']]
        repeater.save()

        info = CaseTriggerInfo(
            domain=DOMAIN,
            case_id=None,
            owner_id='test_location',
            form_question_values=get_form_question_values(form),
        )

        programs = get_programs_by_id(info, repeater.dhis2_config, None)

        self.assertDictEqual(
            programs[program_id]['geometry'],
            {'type': 'NONE', 'coordinates': [-33.6543, 19.1234]}
        )


def test_doctests():
    from corehq.motech.dhis2 import entities_helpers

    results = doctest.testmod(entities_helpers)
    assert results.failed == 0
