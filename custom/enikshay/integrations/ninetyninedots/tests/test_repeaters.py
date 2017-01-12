import json
from datetime import datetime
from django.test import TestCase

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends
from casexml.apps.case.mock import CaseStructure
from corehq.apps.repeaters.models import RepeatRecord
from corehq.apps.repeaters.dbaccessors import delete_all_repeat_records, delete_all_repeaters
from casexml.apps.case.tests.util import delete_all_cases

from custom.enikshay.tests.utils import ENikshayCaseStructureMixin
from custom.enikshay.integrations.ninetyninedots.repeater_generators import RegisterPatientPayloadGenerator
from custom.enikshay.const import PRIMARY_PHONE_NUMBER
from custom.enikshay.integrations.ninetyninedots.repeaters import (
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

    def setUp(self):
        super(TestRegisterPatientRepeater, self).setUp()

        self.repeater = NinetyNineDotsRegisterPatientRepeater(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    @run_with_all_backends
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

    def setUp(self):
        super(TestUpdatePatientRepeater, self).setUp()
        self.repeater = NinetyNineDotsUpdatePatientRepeater(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater.white_listed_case_types = ['person']
        self.repeater.save()

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

    @run_with_all_backends
    def test_trigger(self):
        self.create_case_structure()
        self._update_person({PRIMARY_PHONE_NUMBER: '999999999', })
        self.assertEqual(0, len(self.repeat_records().all()))

        self._create_99dots_registered_case()
        self.assertEqual(0, len(self.repeat_records().all()))

        self._update_person({'name': 'Elrond', })
        self.assertEqual(0, len(self.repeat_records().all()))

        self._update_person({PRIMARY_PHONE_NUMBER: '999999999', })
        self.assertEqual(1, len(self.repeat_records().all()))

    @run_with_all_backends
    def test_trigger_multiple_cases(self):
        """Submitting a form with noop case blocks was throwing an exception
        """
        self.create_case_structure()
        self._create_99dots_registered_case()

        empty_case = CaseStructure(
            case_id=self.episode_id,
        )
        person_case = CaseStructure(
            case_id=self.person_id,
            attrs={
                'case_type': 'person',
                'update': {PRIMARY_PHONE_NUMBER: '9999999999'}
            }
        )

        self.factory.create_or_update_cases([empty_case, person_case])
        self.assertEqual(1, len(self.repeat_records().all()))

    @run_with_all_backends
    def test_create_person_no_episode(self):
        """On registration this was failing hard if a phone number was added but no episode was created
        http://manage.dimagi.com/default.asp?241290#1245284
        """
        self.create_case(self.person)
        self.assertEqual(0, len(self.repeat_records().all()))


class TestRegisterPatientPayloadGenerator(ENikshayCaseStructureMixin, TestCase):

    def setUp(self):
        super(TestRegisterPatientPayloadGenerator, self).setUp()

    def tearDown(self):
        super(TestRegisterPatientPayloadGenerator, self).tearDown()
        delete_all_cases()

    def _assert_payload_equal(self, casedb, expected_numbers):
        expected_payload = json.dumps({
            'beneficiary_id': self.person_id,
            'phone_numbers': expected_numbers,
            'merm_id': casedb[self.person_id].dynamic_case_properties().get('merm_id')
        })
        actual_payload = RegisterPatientPayloadGenerator(None).get_payload(None, casedb[self.episode_id])
        self.assertEqual(expected_payload, actual_payload)

    @run_with_all_backends
    def test_get_payload(self):
        cases = self.create_case_structure()
        expected_numbers = u"+91{}, +91{}".format(
            self.primary_phone_number.replace("0", ""),
            self.secondary_phone_number.replace("0", "")
        )
        self._assert_payload_equal(cases, expected_numbers)

    @run_with_all_backends
    def test_get_payload_no_numbers(self):
        self.primary_phone_number = None
        self.secondary_phone_number = None
        cases = self.create_case_structure()
        self._assert_payload_equal(cases, None)

    @run_with_all_backends
    def test_get_payload_secondary_number_only(self):
        self.primary_phone_number = None
        cases = self.create_case_structure()
        self._assert_payload_equal(cases, u"+91{}".format(self.secondary_phone_number.replace("0", "")))

    @run_with_all_backends
    def test_handle_success(self):
        cases = self.create_case_structure()
        payload_generator = RegisterPatientPayloadGenerator(None)
        payload_generator.handle_success(MockResponse(201, {"success": "hooray"}), cases[self.episode_id], None)
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self.assertEqual(
            updated_episode_case.dynamic_case_properties().get('dots_99_registered'),
            'true'
        )
        self.assertEqual(
            updated_episode_case.dynamic_case_properties().get('dots_99_error'),
            ''
        )

    @run_with_all_backends
    def test_handle_failure(self):
        cases = self.create_case_structure()
        payload_generator = RegisterPatientPayloadGenerator(None)
        error = {
            "error": "Something went terribly wrong",
        }
        payload_generator.handle_failure(MockResponse(400, error), cases[self.episode_id], None)
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self.assertEqual(
            updated_episode_case.dynamic_case_properties().get('dots_99_registered'),
            'false'
        )
        self.assertEqual(
            updated_episode_case.dynamic_case_properties().get('dots_99_error'),
            "400: {}".format(error['error'])
        )
