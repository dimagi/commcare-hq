import json
from datetime import datetime
from django.test import TestCase

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.test_utils import flag_enabled
from custom.enikshay.integrations.nikshay.repeaters import NikshayRegisterPatientRepeater
from custom.enikshay.tests.utils import ENikshayCaseStructureMixin, ENikshayLocationStructureMixin

from custom.enikshay.integrations.nikshay.repeater_generator import (
    NikshayRegisterPatientPayloadGenerator,
    ENIKSHAY_ID,
    get_person_locations,
)
from custom.enikshay.integrations.nikshay.exceptions import NikshayLocationNotFound
from corehq.form_processor.tests.utils import run_with_all_backends
from casexml.apps.case.mock import CaseStructure
from corehq.apps.repeaters.models import RepeatRecord
from corehq.apps.repeaters.dbaccessors import delete_all_repeat_records, delete_all_repeaters
from casexml.apps.case.tests.util import delete_all_cases


class MockResponse(object):
    def __init__(self, status_code, json_data):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data


class NikshayRepeaterTestBase(ENikshayCaseStructureMixin, TestCase):
    def setUp(self):
        super(NikshayRepeaterTestBase, self).setUp()

        delete_all_repeat_records()
        delete_all_repeaters()
        delete_all_cases()

    def tearDown(self):
        super(NikshayRepeaterTestBase, self).tearDown()

        delete_all_repeat_records()
        delete_all_repeaters()
        delete_all_cases()

    def repeat_records(self):
        return RepeatRecord.all(domain=self.domain, due_before=datetime.utcnow())

    def _create_nikshay_enabled_case(self, case_id=None):
        if case_id is None:
            case_id = self.episode_id

        nikshay_enabled_case_on_update = CaseStructure(
            case_id=case_id,
            attrs={
                "create": False,
                "update": dict(
                    episode_pending_registration='no',
                )
            }
        )

        return self.create_case(nikshay_enabled_case_on_update)[0]

    def _create_nikshay_registered_case(self):
        nikshay_registered_case = CaseStructure(
            case_id=self.episode_id,
            attrs={
                'create': False,
                "update": dict(
                    nikshay_registered='true',
                )
            }
        )
        self.create_case(nikshay_registered_case)


class TestNikshayRegisterPatientRepeater(NikshayRepeaterTestBase):

    def setUp(self):
        super(TestNikshayRegisterPatientRepeater, self).setUp()

        self.repeater = NikshayRegisterPatientRepeater(
            domain=self.domain,
            url='case-repeater-url',
            username='test-user'
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    def test_not_available_for_domain(self):
        self.assertFalse(NikshayRegisterPatientRepeater.available_for_domain(self.domain))

    @flag_enabled('NIKSHAY_INTEGRATION')
    def test_available_for_domain(self):
        self.assertTrue(NikshayRegisterPatientRepeater.available_for_domain(self.domain))

    @run_with_all_backends
    def test_trigger(self):
        # nikshay not enabled
        self.create_case(self.episode)
        self.assertEqual(0, len(self.repeat_records().all()))

        # nikshay enabled, should register a repeat record
        self._create_nikshay_enabled_case()
        self.assertEqual(1, len(self.repeat_records().all()))
        #
        # set as registered, should not register a new repeat record
        self._create_nikshay_registered_case()
        self.assertEqual(1, len(self.repeat_records().all()))

    @run_with_all_backends
    def test_trigger_different_case_type(self):
        # different case type
        self.create_case(self.person)
        self._create_nikshay_enabled_case(case_id=self.person_id)
        self.assertEqual(0, len(self.repeat_records().all()))


class TestNikshayRegisterPatientPayloadGenerator(ENikshayLocationStructureMixin, NikshayRepeaterTestBase):
    def setUp(self):
        super(TestNikshayRegisterPatientPayloadGenerator, self).setUp()
        self.cases = self.create_case_structure()
        self.assign_person_to_location(self.phi.location_id)

    @run_with_all_backends
    def test_payload_properties(self):
        episode_case = self._create_nikshay_enabled_case()
        payload = (json.loads(
            NikshayRegisterPatientPayloadGenerator(None).get_payload(None, episode_case))
        )
        self.assertEqual(payload['Source'], ENIKSHAY_ID)
        self.assertEqual(payload['Local_ID'], self.person_id)
        self.assertEqual(payload['regBy'], "tbu-dmdmo01")

        # From Person
        self.assertEqual(payload['pname'], "Pippin")
        self.assertEqual(payload['page'], '20')
        self.assertEqual(payload['pgender'], 'M')
        self.assertEqual(payload['paddress'], 'Mr. Everest')
        self.assertEqual(payload['pmob'], self.primary_phone_number)
        self.assertEqual(payload['cname'], 'Mrs. Everestie')
        self.assertEqual(payload['caddress'], 'Mrs. Everestie')
        self.assertEqual(payload['cmob'], self.secondary_phone_number)
        self.assertEqual(payload['pcategory'], '2')

        # From Episode
        self.assertEqual(payload['sitedetail'], 2)
        self.assertEqual(payload['Ptype'], '6')
        self.assertEqual(payload['poccupation'], 4)
        self.assertEqual(payload['dotname'], 'awesome dot')
        self.assertEqual(payload['dotmob'], '123456789')
        self.assertEqual(payload['disease_classification'], 'EP')
        self.assertEqual(payload['pregdate'], '2014-09-09')
        self.assertEqual(payload['ptbyr'], '2014')
        self.assertEqual(payload['dotpType'], '5')
        self.assertEqual(payload['dotdesignation'], 'ngo_volunteer')
        self.assertEqual(payload['dateofInitiation'], '2015-03-03')

    def _assert_case_property_equal(self, case, case_property, expected_value):
        self.assertEqual(case.dynamic_case_properties().get(case_property), expected_value)

    @run_with_all_backends
    def test_handle_success(self):
        nikshay_id = "NIKSHAY!"
        self._create_nikshay_enabled_case()
        payload_generator = NikshayRegisterPatientPayloadGenerator(None)
        payload_generator.handle_success(
            MockResponse(
                201,
                {
                    "Nikshay_Message": "Success",
                    "Results": [
                        {
                            "FieldName": "NikshayId",
                            "Fieldvalue": nikshay_id,
                        }
                    ]
                }
            ),
            self.cases[self.episode_id],
            None,
        )
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self._assert_case_property_equal(updated_episode_case, 'nikshay_registered', 'true')
        self._assert_case_property_equal(updated_episode_case, 'nikshay_error', '')
        self._assert_case_property_equal(updated_episode_case, 'nikshay_id', nikshay_id)
        self.assertEqual(updated_episode_case.external_id, nikshay_id)

    @run_with_all_backends
    def test_handle_bad_nikshay_response(self):
        self._create_nikshay_enabled_case()
        payload_generator = NikshayRegisterPatientPayloadGenerator(None)
        response = {
            "Nikshay_Message": "Success",
            "Results": [
                {
                    "FieldName": "BadResponse",
                    "Fieldvalue": "Borked",
                }
            ]
        }
        payload_generator.handle_success(
            MockResponse(
                201,
                response,
            ),
            self.cases[self.episode_id],
            None,
        )
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self._assert_case_property_equal(updated_episode_case, 'nikshay_registered', 'false')
        self._assert_case_property_equal(
            updated_episode_case,
            'nikshay_error',
            'No Nikshay ID received: {}'.format(response)
        )

    @run_with_all_backends
    def test_handle_duplicate(self):
        payload_generator = NikshayRegisterPatientPayloadGenerator(None)
        payload_generator.handle_failure(
            MockResponse(
                409,
                {
                    "Nikshay_Message": "Conflict",
                    "Results": [
                        {
                            "FieldName": "NikshayId",
                            "Fieldvalue": "Dublicate Entry"
                        }
                    ]
                }
            ),
            self.cases[self.episode_id],
            None,
        )
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self._assert_case_property_equal(updated_episode_case, 'nikshay_registered', 'true')
        self._assert_case_property_equal(updated_episode_case, 'nikshay_error', 'duplicate')

    @run_with_all_backends
    def test_handle_failure(self):
        message = {
            "Nikshay_Message": "Success",
            "Results": [
                {
                    "FieldName": "NikshayId",
                    "Fieldvalue": "The INSERT statement conflicted with the FOREIGN KEY constraint \"FK_PatientsDetails_TBUnits\". The conflict occurred in database \"nikshay\", table \"dbo.TBUnits\".\u000d\u000a \u000d\u000aDM-ABC-01-16-0001\u000d\u000aThe statement has been terminated."  # noqa. yes, this is a real response.
                }
            ]
        }
        payload_generator = NikshayRegisterPatientPayloadGenerator(None)
        payload_generator.handle_failure(
            MockResponse(
                400,
                message,
            ),
            self.cases[self.episode_id],
            None,
        )
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self._assert_case_property_equal(updated_episode_case, 'nikshay_registered', 'false')
        self._assert_case_property_equal(updated_episode_case, 'nikshay_error', unicode(message))


class TestGetPersonLocations(ENikshayCaseStructureMixin, ENikshayLocationStructureMixin, TestCase):
    def setUp(self):
        super(TestGetPersonLocations, self).setUp()
        self.cases = self.create_case_structure()

    def test_get_person_locations(self):
        self.assign_person_to_location(self.phi.location_id)
        person_case = CaseAccessors(self.domain).get_case(self.person_id)
        expected_locations = {
            'scode': self.sto.metadata['nikshay_code'],
            'dcode': self.dto.metadata['nikshay_code'],
            'tcode': self.tu.metadata['nikshay_code'],
            'dotphi': self.phi.metadata['nikshay_code'],
        }
        self.assertEqual(expected_locations, get_person_locations(person_case))

    def test_nikshay_location_not_found(self):
        self.assign_person_to_location("-")
        person_case = CaseAccessors(self.domain).get_case(self.person_id)
        with self.assertRaises(NikshayLocationNotFound):
            get_person_locations(person_case)
