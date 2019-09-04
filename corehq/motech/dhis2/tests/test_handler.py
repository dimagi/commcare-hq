import json

from django.test.testcases import TestCase

from fakecouch import FakeCouchDb

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.users.models import WebUser
from corehq.motech.dhis2.dhis2_config import Dhis2FormConfig
from corehq.motech.dhis2.forms import Dhis2ConfigForm
from corehq.motech.dhis2.handler import _to_dhis_format
from corehq.motech.dhis2.repeaters import Dhis2Repeater


class TestDhisHandler(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestDhisHandler, cls).setUpClass()

        domain = create_domain('dhis2')
        location_type = LocationType.objects.create(
            domain=domain.name,
            name='test_location_type',
        )
        cls.location = SQLLocation.objects.create(
            domain=domain.name,
            name='test location',
            location_id='test_location',
            location_type=location_type
        )

        cls.user = WebUser.create(domain.name, 'test', 'passwordtest')
        cls.user.set_location(domain.name, cls.location)

    @classmethod
    def tearDownClass(cls):
        cls.location.delete()
        cls.user.delete()
        super(TestDhisHandler, cls).tearDownClass()

    def setUp(self):
        self.db = Dhis2Repeater.get_db()
        self.fakedb = FakeCouchDb()
        Dhis2Repeater.set_db(self.fakedb)

    def tearDown(self):
        Dhis2Repeater.set_db(self.db)

    def test_form_processing(self):
        form = {
            "domain": "dhis2",
            "form": {
                "@xmlns": "test_xmlns",
                "event_date": "2017-05-25T21:06:27.012000",
                "name": "test event",
                "meta": {
                    "location": self.location.location_id,
                    "timeEnd": "2017-05-25T21:06:27.012000",
                    "timeStart": "2017-05-25T21:06:17.739000",
                    "userID": self.user.user_id,
                    "username": self.user.username
                }
            },
            "received_on": "2017-05-25T21:06:27.275256Z",
        }
        config = {
            'form_configs': json.dumps([{
                'xmlns': 'test_xmlns',
                'program_id': 'test program',
                'event_date': {
                    'doc_type': 'FormQuestion',
                    'form_question': '/data/event_date'
                },
                'event_status': 'COMPLETED',
                'org_unit_id': {
                    'doc_type': 'ConstantString',
                    'value': 'dhis2_location_id'
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
        repeater.dhis2_config.form_configs = list(map(Dhis2FormConfig.wrap, data['form_configs']))
        repeater.save()
        dhis_format = _to_dhis_format(repeater.dhis2_config.form_configs[0], form)
        self.assertDictEqual(
            {
                'dataValues': [
                    {
                        'dataElement': 'dhis2_element_id',
                        'value': 'test event'
                    }
                ],
                'status': 'COMPLETED',
                'program': 'test program',
                'eventDate': '2017-05-25',
                'orgUnit': 'dhis2_location_id'
            },
            dhis_format
        )
