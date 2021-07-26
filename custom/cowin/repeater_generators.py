import json

from django.core.serializers.json import DjangoJSONEncoder

from corehq.motech.repeaters.repeater_generators import (
    CaseRepeaterJsonPayloadGenerator,
)


class BeneficiaryRegistrationPayloadGenerator(CaseRepeaterJsonPayloadGenerator):
    def get_payload(self, repeat_record, cowin_api_data_registration_case):
        data = {
            "name": cowin_api_data_registration_case.get_case_property('beneficiary_name'),
            "birth_year": cowin_api_data_registration_case.get_case_property('birth_year'),
            "gender_id": cowin_api_data_registration_case.get_case_property('gender_id'),
            "mobile_number": cowin_api_data_registration_case.get_case_property('mobile_number'),
            "photo_id_type": cowin_api_data_registration_case.get_case_property('photo_id_type'),
            "photo_id_number": cowin_api_data_registration_case.get_case_property('photo_id_number'),
            "consent_version": cowin_api_data_registration_case.get_case_property('consent_version'),
        }
        return json.dumps(data, cls=DjangoJSONEncoder)


class BeneficiaryVaccinationPayloadGenerator(CaseRepeaterJsonPayloadGenerator):
    def get_payload(self, repeat_record, cowin_api_data_vaccination_case):
        data = {
            "beneficiary_reference_id": cowin_api_data_vaccination_case.get_case_property(
                'beneficiary_reference_id'),
            "center_id": cowin_api_data_vaccination_case.get_case_property('center_id'),
            "vaccine": cowin_api_data_vaccination_case.get_case_property('vaccine'),
            "vaccine_batch": cowin_api_data_vaccination_case.get_case_property('vaccine_batch'),
            "vaccinator_name": cowin_api_data_vaccination_case.get_case_property('vaccinator_name'),
        }
        if cowin_api_data_vaccination_case.get_case_property('dose') == '1':
            data.update({
                "dose": 1,
                "dose1_date": cowin_api_data_vaccination_case.get_case_property('dose1_date'),
            })
        elif cowin_api_data_vaccination_case.get_case_property('dose') == '2':
            data.update({
                "dose": 2,
                "dose2_date": cowin_api_data_vaccination_case.get_case_property('dose2_date'),
            })
        return json.dumps(data, cls=DjangoJSONEncoder)
