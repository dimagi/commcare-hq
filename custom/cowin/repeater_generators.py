import json

from django.core.serializers.json import DjangoJSONEncoder

from corehq.motech.repeaters.repeater_generators import (
    CaseRepeaterJsonPayloadGenerator,
)


class BeneficiaryRegistrationPayloadGenerator(CaseRepeaterJsonPayloadGenerator):
    def get_payload(self, repeat_record, beneficiary_case):
        data = {
            "name": beneficiary_case.get_case_property('name'),
            "birth_year": beneficiary_case.get_case_property('birth_year'),
            "gender_id": beneficiary_case.get_case_property('gender_id'),
            "mobile_number": beneficiary_case.get_case_property('mobile_number'),
            "photo_id_type": beneficiary_case.get_case_property('photo_id_type'),
            "photo_id_number": beneficiary_case.get_case_property('photo_id_number'),
            "consent_version": "1"
        }
        return json.dumps(data, cls=DjangoJSONEncoder)


class BeneficiaryVaccinationPayloadGenerator(CaseRepeaterJsonPayloadGenerator):
    def get_payload(self, repeat_record, vaccination_case):
        data = {
            "beneficiary_reference_id": vaccination_case.get_case_property('cowin_id'),
            "center_id": vaccination_case.get_case_property('center_id'),
            "vaccine": vaccination_case.get_case_property('vaccine'),
            "vaccine_batch": vaccination_case.get_case_property('vaccine_batch'),
            "vaccinator_name": vaccination_case.get_case_property('vaccinator_name'),
        }
        if vaccination_case.get_case_property('dose') == '1':
            data.update({
                "dose": 1,
                "dose1_date": vaccination_case.get_case_property('dose1_date'),
            })
        elif vaccination_case.get_case_property('dose') == '2':
            data.update({
                "dose": 2,
                "dose1_date": vaccination_case.get_case_property('dose1_date'),
                "dose2_date": vaccination_case.get_case_property('dose2_date'),
            })
        return json.dumps(data, cls=DjangoJSONEncoder)
