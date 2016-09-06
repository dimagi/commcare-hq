import json
from datetime import datetime
from collections import namedtuple
from django.test import TestCase

from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from casexml.apps.case.mock import CaseStructure
from corehq.apps.repeaters.models import RepeatRecord
from corehq.apps.repeaters.dbaccessors import delete_all_repeat_records, delete_all_repeaters
from casexml.apps.case.tests.util import delete_all_cases

from custom.enikshay.tests.utils import ENikshayCaseStructureMixin
from custom.enikshay.integrations.ninetyninedots.repeater_generators import RegisterPatientPayloadGenerator
from custom.enikshay.integrations.ninetyninedots.repeaters import NinetyNineDotsRegisterPatientRepeater


class TestRegisterPatientRepeater(ENikshayCaseStructureMixin, TestCase):
    def setUp(self):
        super(TestRegisterPatientRepeater, self).setUp()
        delete_all_repeat_records()
        delete_all_repeaters()
        delete_all_cases()
        self.repeater = NinetyNineDotsRegisterPatientRepeater(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater.save()

    def tearDown(self):
        super(TestRegisterPatientRepeater, self).tearDown()
        delete_all_repeat_records()
        delete_all_repeaters()
        delete_all_cases()

    @classmethod
    def repeat_records(cls, domain_name):
        return RepeatRecord.all(domain=domain_name, due_before=datetime.utcnow())

    @run_with_all_backends
    def test_trigger(self):
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

        # 99dots not enabled
        self.create_case(self.episode)
        self.assertEqual(0, len(self.repeat_records(self.domain).all()))

        # enable 99dots, should register a repeat record
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
        self.assertEqual(1, len(self.repeat_records(self.domain).all()))

        # set as registered, shouldn't register a new repeat record
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
        self.assertEqual(1, len(self.repeat_records(self.domain).all()))


class TestRegisterPatientPayloadGenerator(ENikshayCaseStructureMixin, TestCase):
    def setUp(self):
        super(TestRegisterPatientPayloadGenerator, self).setUp()
        self.cases = self.create_case_structure()

    @run_with_all_backends
    def test_get_payload(self):
        payload_generator = RegisterPatientPayloadGenerator(None)
        expected_numbers = u"+91{}, +91{}".format(
            self.cases[self.person_id].dynamic_case_properties()['mobile_number'].replace("0", ""),
            self.cases[self.person_id].dynamic_case_properties()['backup_number'].replace("0", "")
        )
        expected_payload = json.dumps({
            'beneficiary_id': self.person_id,
            'phone_numbers': expected_numbers,
        })
        actual_payload = payload_generator.get_payload(None, self.cases[self.episode_id])
        self.assertEqual(expected_payload, actual_payload)

    @run_with_all_backends
    def test_handle_success(self):
        payload_generator = RegisterPatientPayloadGenerator(None)
        Response = namedtuple("Response", 'status_code')
        payload_generator.handle_success(Response(201), self.cases[self.episode_id])
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
        payload_generator = RegisterPatientPayloadGenerator(None)
        Response = namedtuple("Response", 'status_code message')
        error = {
            "error": "Something went terribly wrong",
        }
        payload_generator.handle_failure(Response(400, json.dumps(error)), self.cases[self.episode_id])
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self.assertEqual(
            updated_episode_case.dynamic_case_properties().get('dots_99_registered'),
            'false'
        )
        self.assertEqual(
            updated_episode_case.dynamic_case_properties().get('dots_99_error'),
            "400: {}".format(error['error'])
        )
