import json
from datetime import datetime
from django.test import TestCase
from django.test.utils import override_settings

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from casexml.apps.case.mock import CaseStructure
from corehq.apps.repeaters.models import RepeatRecord
from corehq.apps.repeaters.dbaccessors import delete_all_repeat_records, delete_all_repeaters
from casexml.apps.case.tests.util import delete_all_cases

from custom.enikshay.tests.utils import ENikshayCaseStructureMixin
from custom.enikshay.integrations.ninetyninedots.repeater_generators import RegisterPatientPayloadGenerator
from custom.enikshay.integrations.ninetyninedots.repeaters import(
    NinetyNineDotsRegisterPatientRepeater,
    NinetyNineDotsUpdatePatientRepeater
)


class MockResponse(object):
    def __init__(self, status_code, json_data):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data


class ENikshayRepeaterTestBase(ENikshayCaseStructureMixin, TestCase):
    def setUp(self):
        super(ENikshayRepeaterTestBase, self).setUp()

        delete_all_repeat_records()
        delete_all_repeaters()
        delete_all_cases()

    def tearDown(self):
        super(ENikshayRepeaterTestBase, self).tearDown()

        delete_all_repeat_records()
        delete_all_repeaters()
        delete_all_cases()

    def repeat_records(self):
        return RepeatRecord.all(domain=self.domain, due_before=datetime.utcnow())

    def _create_99dots_enabled_case(self):
        dots_enabled_case = CaseStructure(
            case_id=self.episode_id,
            attrs={
                'case_type': 'episode',
                "update": dict(
                    dots_99_enabled='true',
                )
            }
        )
        self.create_case(dots_enabled_case)

    def _create_99dots_registered_case(self):
        dots_registered_case = CaseStructure(
            case_id=self.episode_id,
            attrs={
                'create': True,
                'case_type': 'episode',
                "update": dict(
                    dots_99_registered='true',
                )
            }
        )
        self.create_case(dots_registered_case)


class TestRegisterPatientRepeater(ENikshayRepeaterTestBase):

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def setUp(self):
        super(TestRegisterPatientRepeater, self).setUp()

        self.repeater = NinetyNineDotsRegisterPatientRepeater(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_trigger(self):
        # 99dots not enabled
        self.create_case(self.episode)
        self.assertEqual(0, len(self.repeat_records().all()))

        # enable 99dots, should register a repeat record
        self._create_99dots_enabled_case()
        self.assertEqual(1, len(self.repeat_records().all()))

        # set as registered, shouldn't register a new repeat record
        self._create_99dots_registered_case()
        self.assertEqual(1, len(self.repeat_records().all()))


class TestUpdatePatientRepeater(ENikshayRepeaterTestBase):

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def setUp(self):
        super(TestUpdatePatientRepeater, self).setUp()
        self.repeater = NinetyNineDotsUpdatePatientRepeater(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater.white_listed_case_types = ['person']
        self.repeater.save()
        self.create_case_structure()

    def _update_person(self, case_properties):
        return self.create_case(
            CaseStructure(
                case_id=self.person_id,
                attrs={
                    "case_type": "person",
                    "update": case_properties,
                }
            )
        )

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_trigger(self):
        self._update_person({'mobile_number': '999999999', })
        self.assertEqual(0, len(self.repeat_records().all()))

        self._create_99dots_registered_case()
        self.assertEqual(0, len(self.repeat_records().all()))

        self._update_person({'name': 'Elrond', })
        self.assertEqual(0, len(self.repeat_records().all()))

        self._update_person({'mobile_number': '999999999', })
        self.assertEqual(1, len(self.repeat_records().all()))


class TestRegisterPatientPayloadGenerator(ENikshayCaseStructureMixin, TestCase):

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def setUp(self):
        super(TestRegisterPatientPayloadGenerator, self).setUp()
        self.cases = self.create_case_structure()

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def tearDown(self):
        super(TestRegisterPatientPayloadGenerator, self).tearDown()
        delete_all_cases()

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_get_payload(self):
        payload_generator = RegisterPatientPayloadGenerator(None)
        person = self.cases[self.person_id].dynamic_case_properties()
        expected_numbers = u"+91{}, +91{}".format(
            person['mobile_number'].replace("0", ""),
            person['backup_number'].replace("0", "")
        )
        expected_payload = json.dumps({
            'beneficiary_id': self.person_id,
            'phone_numbers': expected_numbers,
            'merm_id': person['merm_id']
        })
        actual_payload = payload_generator.get_payload(None, self.cases[self.episode_id])
        self.assertEqual(expected_payload, actual_payload)

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_handle_success(self):
        payload_generator = RegisterPatientPayloadGenerator(None)
        payload_generator.handle_success(MockResponse(201, {"success": "hooray"}), self.cases[self.episode_id])
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self.assertEqual(
            updated_episode_case.dynamic_case_properties().get('dots_99_registered'),
            'true'
        )
        self.assertEqual(
            updated_episode_case.dynamic_case_properties().get('dots_99_error'),
            ''
        )

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_handle_failure(self):
        payload_generator = RegisterPatientPayloadGenerator(None)
        error = {
            "error": "Something went terribly wrong",
        }
        payload_generator.handle_failure(MockResponse(400, error), self.cases[self.episode_id])
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self.assertEqual(
            updated_episode_case.dynamic_case_properties().get('dots_99_registered'),
            'false'
        )
        self.assertEqual(
            updated_episode_case.dynamic_case_properties().get('dots_99_error'),
            "400: {}".format(error['error'])
        )
