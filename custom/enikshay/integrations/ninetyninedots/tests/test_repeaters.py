import json
from django.test import TestCase
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
