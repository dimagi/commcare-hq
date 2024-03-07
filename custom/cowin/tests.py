import datetime
import json
import uuid

from django.test import SimpleTestCase

import requests
from unittest.mock import PropertyMock, patch

from corehq.form_processor.models import CommCareCase
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import SQLRepeatRecord
from custom.cowin.const import (
    COWIN_API_DATA_REGISTRATION_IDENTIFIER,
    COWIN_API_DATA_VACCINATION_IDENTIFIER,
)
from custom.cowin.repeater_generators import (
    BeneficiaryRegistrationPayloadGenerator,
    BeneficiaryVaccinationPayloadGenerator,
)
from custom.cowin.repeaters import (
    BeneficiaryRegistrationRepeater,
    BeneficiaryVaccinationRepeater,
)


class TestRepeaters(SimpleTestCase):
    domain = 'test-cowin'

    @patch('corehq.motech.repeaters.models.Repeater.connection_settings', new_callable=PropertyMock)
    @patch('corehq.motech.repeaters.models.CaseRepeater.payload_doc')
    def test_registration_payload(self, payload_doc_mock, connection_settings_mock):
        connection_settings_mock.return_value = ConnectionSettings(password="secure-api-key")

        case_id = uuid.uuid4().hex
        case_json = {
            'beneficiary_name': 'Nitish Dube',
            'birth_year': '2000',
            'gender_id': '1',
            'mobile_number': '9999999999',
            'photo_id_type': '1',
            'photo_id_number': '1234',
            'consent_version': "1"
        }
        case = CommCareCase(domain=self.domain, type='cowin_api_data', case_id=case_id, case_json=case_json,
                            server_modified_on=datetime.datetime.utcnow())
        payload_doc_mock.return_value = case

        repeater = BeneficiaryRegistrationRepeater()
        generator = BeneficiaryRegistrationPayloadGenerator(repeater)
        repeat_record = SQLRepeatRecord()

        self.assertEqual(repeater.get_headers(repeat_record)['X-Api-Key'], "secure-api-key")

        payload = generator.get_payload(repeat_record=None, cowin_api_data_registration_case=case)
        self.assertDictEqual(
            json.loads(payload),
            {
                'name': 'Nitish Dube',
                'birth_year': '2000',
                'gender_id': 1,
                'mobile_number': '9999999999',
                "photo_id_type": 1,
                'photo_id_number': '1234',
                "consent_version": "1"
            }
        )

    @patch('corehq.motech.repeaters.models.SQLRepeatRecord.handle_success', lambda *_: None)
    @patch('corehq.motech.repeaters.models.SQLRepeatRecord.repeater', new_callable=PropertyMock)
    @patch('corehq.motech.repeaters.models.CaseRepeater.payload_doc')
    @patch('custom.cowin.repeaters.update_case')
    @patch('requests.Response.json')
    def test_registration_response(self, json_response_mock, update_case_mock, payload_doc_mock,
                                   repeat_record_repeater_mock):
        case_id = uuid.uuid4().hex
        person_case_id = uuid.uuid4().hex
        case_json = {
            'person_case_id': person_case_id,
            'api': COWIN_API_DATA_REGISTRATION_IDENTIFIER
        }
        case = CommCareCase(domain=self.domain, type='cowin_api_data', case_id=case_id, case_json=case_json,
                            server_modified_on=datetime.datetime.utcnow())
        payload_doc_mock.return_value = case

        response_json = {
            "beneficiary_reference_id": "1234567890123",
            "isNewAccount": "Y"
        }

        response = requests.Response()
        response.status_code = 200
        json_response_mock.return_value = response_json

        repeat_record = SQLRepeatRecord(payload_id=case_id)
        repeater = BeneficiaryRegistrationRepeater(domain=self.domain)
        repeat_record_repeater_mock.return_value = repeater

        repeater.handle_response(response, repeat_record)

        update_case_mock.assert_called_with(
            self.domain, person_case_id, case_properties={'cowin_beneficiary_reference_id': "1234567890123"},
            device_id='custom.cowin.repeaters.BeneficiaryRegistrationRepeater'
        )

    @patch('corehq.motech.repeaters.models.Repeater.connection_settings', new_callable=PropertyMock)
    @patch('corehq.motech.repeaters.models.CaseRepeater.payload_doc')
    def test_vaccination_payload(self, payload_doc_mock, connection_settings_mock):
        connection_settings_mock.return_value = ConnectionSettings(password="my-secure-api-key")

        case_id = uuid.uuid4().hex
        case = CommCareCase(domain=self.domain, type='cowin_api_data', case_id=case_id,
                            server_modified_on=datetime.datetime.utcnow())
        payload_doc_mock.return_value = case

        repeater = BeneficiaryVaccinationRepeater()
        generator = BeneficiaryVaccinationPayloadGenerator(repeater)
        repeat_record = SQLRepeatRecord()

        self.assertEqual(repeater.get_headers(repeat_record)['X-Api-Key'], "my-secure-api-key")

        # 1st dose
        case.case_json = {
            'beneficiary_reference_id': '1234567890123',
            'center_id': "1234",
            'vaccine': "COVISHIELD",
            'vaccine_batch': '123456',
            'dose': '1',
            'dose1_date': "2020-11-29",
            'vaccinator_name': 'Neelima',
        }

        payload = generator.get_payload(repeat_record=None, cowin_api_data_vaccination_case=case)
        self.assertDictEqual(
            json.loads(payload),
            {
                "beneficiary_reference_id": "1234567890123",
                "center_id": 1234,
                "vaccine": "COVISHIELD",
                "vaccine_batch": "123456",
                "dose": 1,
                "dose1_date": "29-11-2020",
                "vaccinator_name": "Neelima"
            }
        )

        # 2nd dose
        case.case_json = {
            'beneficiary_reference_id': '1234567890123',
            'center_id': "1234",
            'vaccine': "COVISHIELD",
            'vaccine_batch': '123456',
            'dose': '2',
            'dose2_date': "2020-12-29",
            'vaccinator_name': 'Sumanthra',
        }

        payload = generator.get_payload(repeat_record=None, cowin_api_data_vaccination_case=case)
        self.assertDictEqual(
            json.loads(payload),
            {
                "beneficiary_reference_id": "1234567890123",
                "center_id": 1234,
                "vaccine": "COVISHIELD",
                "vaccine_batch": "123456",
                "dose": 2,
                "dose2_date": "29-12-2020",
                "vaccinator_name": "Sumanthra"
            }
        )

    @patch('corehq.motech.repeaters.models.SQLRepeatRecord.handle_success', lambda *_: None)
    @patch('corehq.motech.repeaters.models.SQLRepeatRecord.repeater', new_callable=PropertyMock)
    @patch('corehq.motech.repeaters.models.CaseRepeater.payload_doc')
    @patch('custom.cowin.repeaters.update_case')
    def test_vaccination_response(self, update_case_mock, payload_doc_mock, repeat_record_repeater_mock):
        case_id = uuid.uuid4().hex
        person_case_id = uuid.uuid4().hex
        case_json = {
            'person_case_id': person_case_id,
            'api': COWIN_API_DATA_VACCINATION_IDENTIFIER,
            'dose': "1"
        }
        case = CommCareCase(domain=self.domain, type='cowin_api_data', case_id=case_id, case_json=case_json,
                            server_modified_on=datetime.datetime.utcnow())
        payload_doc_mock.return_value = case

        response = requests.Response()
        response.status_code = 204

        repeat_record = SQLRepeatRecord(payload_id=case_id)
        repeater = BeneficiaryVaccinationRepeater(domain=self.domain)

        repeat_record_repeater_mock.return_value = repeater
        repeater.handle_response(response, repeat_record)

        update_case_mock.assert_called_with(
            self.domain, person_case_id, case_properties={'dose_1_notified': True},
            device_id='custom.cowin.repeaters.BeneficiaryVaccinationRepeater'
        )
