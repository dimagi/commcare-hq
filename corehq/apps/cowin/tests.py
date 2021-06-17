import json
import uuid

from django.test import SimpleTestCase

from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.cowin.repeater_generators import (
    BeneficiaryRegistrationPayloadGenerator,
    BeneficiaryVaccinationPayloadGenerator,
)
from corehq.apps.cowin.repeaters import (
    BeneficiaryRegistrationRepeater,
    BeneficiaryVaccinationRepeater,
)
from corehq.apps.cowin.views import AppointmentResultsFixture
from corehq.form_processor.models import CommCareCaseSQL

DUMMY_RESPONSE = {
    "sessions": [{
        "center_id": 1234,
        "name": "District General Hostpital",
        "name_l": "",
        "address": "45 M G Road",
        "address_l": "",
        "state_name": "Maharashtra",
        "state_name_l": "",
        "district_name": "Satara",
        "district_name_l": "",
        "block_name": "Jaoli",
        "block_name_l": "",
        "pincode": "413608",
        "lat": 28.7,
        "long": 77.1,
        "from": "09:00:00",
        "to": "18:00:00",
        "fee_type": "Paid",
        "fee": "250",
        "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "date": "31-05-2021",
        "available_capacity": 50,
        "available_capacity_dose1": 25,
        "available_capacity_dose2": 25,
        "min_age_limit": 18,
        "vaccine": "COVISHIELD",
        "slots": [
            "FORENOON",
            "AFTERNOON"
        ]
    }]
}


class TestAppointmentResultsFixture(SimpleTestCase, TestXmlMixin):
    def test_fixture(self):
        fixture = AppointmentResultsFixture(DUMMY_RESPONSE['sessions']).fixture
        self.assertXmlPartialEqual(
            """
            <partial>
              <results id="appointments">
                <appointment>
                  <name>District General Hostpital</name>
                  <address>45 M G Road</address>
                  <state_name>Maharashtra</state_name>
                  <district_name>Satara</district_name>
                  <block_name>Jaoli</block_name>
                  <pincode>413608</pincode>
                  <from>09:00:00</from>
                  <to>18:00:00</to>
                  <fee_type>Paid</fee_type>
                  <fee>250</fee>
                  <session_id>3fa85f64-5717-4562-b3fc-2c963f66afa6</session_id>
                  <date>31-05-2021</date>
                  <available_capacity>50</available_capacity>
                  <available_capacity_dose1>25</available_capacity_dose1>
                  <available_capacity_dose2>25</available_capacity_dose2>
                  <min_age_limit>18</min_age_limit>
                  <vaccine>COVISHIELD</vaccine>
                  <slots>[\'FORENOON\', \'AFTERNOON\']</slots>
                </appointment>
              </results>
            </partial>
            """,
            fixture,
            "."
        )


class TestRepeaters(SimpleTestCase):
    domain = 'test-cowin'

    def test_registration_payload(self):
        case_id = uuid.uuid4().hex
        case_json = {
            'name': 'Nitish Dube',
            'birth_year': '2000',
            'gender_id': 1,
            'mobile_number': '9999999999',
            'aadhaar_number': 'XXXXXXXX1234',
        }
        case = CommCareCaseSQL(domain=self.domain, type='beneficiary', case_id=case_id, case_json=case_json)
        repeater = BeneficiaryRegistrationRepeater()
        generator = BeneficiaryRegistrationPayloadGenerator(repeater)
        payload = generator.get_payload(repeat_record=None, beneficiary_case=case)
        self.assertDictEqual(
            json.loads(payload),
            {
                'name': 'Nitish Dube',
                'birth_year': '2000',
                'gender_id': 1,
                'mobile_number': '9999999999',
                "photo_id_type": 1,
                'photo_id_number': 'XXXXXXXX1234',
                "consent_version": "1"
            }
        )

    def test_vaccination_payload(self):
        case_id = uuid.uuid4().hex
        case = CommCareCaseSQL(domain=self.domain, type='vaccination', case_id=case_id)
        repeater = BeneficiaryVaccinationRepeater()
        generator = BeneficiaryVaccinationPayloadGenerator(repeater)

        # 1st dose
        case.case_json = {
            'cowin_id': '1234567890123',
            'center_id': 1234,
            'vaccine': "COVISHIELD",
            'vaccine_batch': '123456',
            'dose': 1,
            'dose1_date': "01-01-2020",
            'vaccinator_name': 'Neelima',
        }

        payload = generator.get_payload(repeat_record=None, vaccination_case=case)
        self.assertDictEqual(
            json.loads(payload),
            {
                "beneficiary_reference_id": "1234567890123",
                "center_id": 1234,
                "vaccine": "COVISHIELD",
                "vaccine_batch": "123456",
                "dose": 1,
                "dose1_date": "01-01-2020",
                "vaccinator_name": "Neelima"
            }
        )

        # 2nd dose
        case.case_json.update({
            'dose': 2,
            'dose2_date': "01-02-2020",
            'vaccinator_name': 'Sumanthra',
        })

        payload = generator.get_payload(repeat_record=None, vaccination_case=case)
        self.assertDictEqual(
            json.loads(payload),
            {
                "beneficiary_reference_id": "1234567890123",
                "center_id": 1234,
                "vaccine": "COVISHIELD",
                "vaccine_batch": "123456",
                "dose": 2,
                "dose1_date": "01-01-2020",
                "dose2_date": "01-02-2020",
                "vaccinator_name": "Sumanthra"
            }
        )
