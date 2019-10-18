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
        data = self._setup_names(case)
        data.update({
            "gender": self._gender(case.get_case_property('gender')),
            "villagecode": 442639,
            "subdistrictcode": 3318,
            "districtcode": 378,
            "statecode": 22,
            "dateofbirth": case.get_case_property('date_of_birth') or "",
            "mobileno": case.get_case_property('mobile_number') or "",
            "email": "",
            "govt_id_name": "",
            "govt_id_number": ""
        })
        return json.dumps(data, cls=DjangoJSONEncoder)

    def _setup_names(self, case):
        data = {}
        self._setup_name(case.name, 'beneficaryname', 'namelocal', data)
        for case_property, key_name, key_name_local in [
            ("mothers_name", "mothername", "mothernamelocal"),
            ("fathers_name", "fathername", "fathernamelocal"),
            ("husbands_name", "husbandname", "husbandnamelocal"),
        ]:
            self._setup_name(case.get_case_property(case_property), key_name, key_name_local, data)
        return data

    def _setup_name(self, name, key_name, key_name_local, data):
        data[key_name] = ""
        data[key_name_local] = ""
        if name and self._has_special_chars(name):
            data[key_name_local] = name
        else:
            data[key_name] = name

    @staticmethod
    def _has_special_chars(value):
        try:
            value.encode(encoding='utf-8').decode('ascii')
        except UnicodeDecodeError:
            return True
        return False

    def handle_success(self, response, case, repeat_record):
        phi_id = response.json().get('result', [{}])[0].get('phi_id', None)
        if phi_id:
            update_case(case.domain, case.case_id,
                        {'phid_for_beneficiary': phi_id, 'phid_valid': 'yes'},
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
