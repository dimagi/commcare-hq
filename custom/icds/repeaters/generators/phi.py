import json

from django.core.serializers.json import DjangoJSONEncoder

from corehq import toggles
from corehq.apps.hqcase.utils import update_case
from corehq.motech.repeaters.repeater_generators import (
    CaseRepeaterJsonPayloadGenerator,
)


class BasePayloadGenerator(CaseRepeaterJsonPayloadGenerator):
    @staticmethod
    def enabled_for_domain(domain):
        return toggles.PHI_CAS_INTEGRATION.enabled(domain)


class SearchByParamsPayloadGenerator(BasePayloadGenerator):
    @staticmethod
    def _gender(gender):
        if gender:
            if gender == 'male':
                return 'M'
            elif gender == 'female':
                return 'F'
        return ""

    def get_payload(self, repeat_record, case):
        data = {
            "beneficaryname": case.name,
            "fathername": case.get_case_property('fathers_name') or "",
            "husbandname": case.get_case_property('husbands_name') or "",
            "mothername": case.get_case_property('mothers_name') or "",
            "gender": self._gender(case.get_case_property('gender')),
            "villagecode": 442639,
            "subdistrictcode": 3318,
            "districtcode": 378,
            "statecode": 22,
            "dateofbirth": case.get_case_property('date_of_birth') or "",
            "mobileno": case.get_case_property('mobile_number') or "",
            "namelocal": case.name,
            "mothernamelocal": case.get_case_property('mothers_name') or "",
            "fathernamelocal": case.get_case_property('fathers_name') or "",
            "husbandnamelocal": case.get_case_property('husbands_name') or "",
            "email": "",
            "govt_id_name": "",
            "govt_id_number": ""
        }
        return json.dumps(data, cls=DjangoJSONEncoder)

    def handle_success(self, response, case, repeat_record):
        phi_id = response.json().get('result', [{}])[0].get('phi_id', None)
        if phi_id:
            update_case(case.domain, case.case_id, {'phid_for_beneficiary': phi_id},
                        device_id=__name__ + ".search")


class ValidatePHIDPayloadGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, payload_doc):
        data = {'phi_id': payload_doc.get_case_property('phid_for_beneficiary')}
        return json.dumps(data, cls=DjangoJSONEncoder)

    def handle_success(self, response, case, repeat_record):
        case_update = {'phid_validated': 'yes'}
        if response.json()['result'] == 'true':
            case_update['phid_valid'] = 'yes'
        else:
            case_update['phid_valid'] = 'no'
        update_case(case.domain, case.case_id, case_update,
                    device_id=__name__ + ".validate")
