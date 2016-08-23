import json
from collections import namedtuple
from django.test import TestCase

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from custom.enikshay.tests.utils import ENikshayCaseStructureMixin
from custom.enikshay.integrations.ninetyninedots.repeater_generators import RegisterPatientPayloadGenerator


class TestRegisterPatientPayloadGenerator(ENikshayCaseStructureMixin, TestCase):
    def setUp(self):
        super(TestRegisterPatientPayloadGenerator, self).setUp()
        self.cases = self.create_case_structure()

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
