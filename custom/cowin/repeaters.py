from django.utils.translation import ugettext_lazy as _

from corehq import toggles
from corehq.apps.hqcase.utils import update_case
from corehq.motech.repeaters.models import CaseRepeater
from custom.cowin.repeater_generators import (
    BeneficiaryRegistrationPayloadGenerator,
    BeneficiaryVaccinationPayloadGenerator,
)


class BaseCOWINRepeater(CaseRepeater):
    class Meta:
        app_label = 'repeaters'

    @classmethod
    def available_for_domain(cls, domain):
        return toggles.COWIN_INTEGRATION.enabled(domain)

    def get_headers(self, repeat_record):
        headers = super().get_headers(repeat_record)

        headers.update({
            'Accept-Language': 'en_US',
            'User-Agent': '',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Api-Key': self.connection_settings.plaintext_password,
        })
        return headers


class BeneficiaryRegistrationRepeater(BaseCOWINRepeater):
    payload_generator_classes = (BeneficiaryRegistrationPayloadGenerator,)
    friendly_name = _("Register beneficiaries on COWIN")

    def handle_response(self, response, repeat_record):
        attempt = super().handle_response(response, repeat_record)
        # successful response is always 200. 40x and 500 are errors
        if response.status_code == 200:
            beneficiary_reference_id = response.json()['beneficiary_reference_id']
            update_case(self.domain, repeat_record.payload_id,
                        case_properties={'cowin_id': beneficiary_reference_id},
                        device_id=__name__ + '.BeneficiaryRegistrationRepeater')
        return attempt

    def allowed_to_forward(self, case):
        allowed = super().allowed_to_forward(case)
        if allowed:
            return not bool(case.get_case_property('cowin_id'))
        return allowed


class BeneficiaryVaccinationRepeater(BaseCOWINRepeater):
    payload_generator_classes = (BeneficiaryVaccinationPayloadGenerator,)
    friendly_name = _("Update vaccination for beneficiaries on COWIN")

    def allowed_to_forward(self, case):
        allowed = super().allowed_to_forward(case)
        if allowed:
            return bool(case.get_case_property('cowin_id'))
        return allowed
