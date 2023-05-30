from django.utils.translation import gettext_lazy as _

from corehq import toggles
from corehq.apps.hqcase.utils import update_case
from corehq.motech.repeaters.models import CaseRepeater
from custom.cowin.const import COWIN_API_DATA_REGISTRATION_IDENTIFIER, COWIN_API_DATA_VACCINATION_IDENTIFIER
from custom.cowin.repeater_generators import (
    BeneficiaryRegistrationPayloadGenerator,
    BeneficiaryVaccinationPayloadGenerator,
)


class BaseCOWINRepeater(CaseRepeater):
    class Meta:
        proxy = True
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

    class Meta:
        app_label = 'repeaters'
        proxy = True

    payload_generator_classes = (BeneficiaryRegistrationPayloadGenerator,)
    friendly_name = _("Register beneficiaries on COWIN")

    def handle_response(self, response, repeat_record):
        attempt = super().handle_response(response, repeat_record)
        # successful response is always 200. 40x and 500 are errors
        if response.status_code == 200:
            cowin_api_data_registration_case = repeat_record.repeater.payload_doc(repeat_record)
            person_case_id = cowin_api_data_registration_case.get_case_property("person_case_id")
            # Ideally person case id should always be present
            # Simply ignore cases that don't have that and don't try again
            if person_case_id:
                beneficiary_reference_id = response.json()['beneficiary_reference_id']
                update_case(self.domain, person_case_id,
                            case_properties={'cowin_beneficiary_reference_id': beneficiary_reference_id},
                            device_id=__name__ + '.BeneficiaryRegistrationRepeater')
        return attempt

    def allowed_to_forward(self, case):
        allowed = super().allowed_to_forward(case)
        if allowed:
            return (
                not bool(case.get_case_property('cowin_beneficiary_reference_id'))
                and case.get_case_property('api') == COWIN_API_DATA_REGISTRATION_IDENTIFIER
            )
        return allowed


class BeneficiaryVaccinationRepeater(BaseCOWINRepeater):

    class Meta:
        app_label = 'repeaters'
        proxy = True

    payload_generator_classes = (BeneficiaryVaccinationPayloadGenerator,)
    friendly_name = _("Update vaccination for beneficiaries on COWIN")

    def handle_response(self, response, repeat_record):
        attempt = super().handle_response(response, repeat_record)
        # successful response is always 204
        if response.status_code == 204:
            cowin_api_data_vaccination_case = repeat_record.repeater.payload_doc(repeat_record)
            person_case_id = cowin_api_data_vaccination_case.get_case_property("person_case_id")
            dose_number = cowin_api_data_vaccination_case.get_case_property("dose")
            # Ideally person case id should always be present
            # Simply ignore cases that don't have that and don't try again
            if person_case_id:
                update_case(self.domain, person_case_id,
                            case_properties={f'dose_{dose_number}_notified': True},
                            device_id=__name__ + '.BeneficiaryVaccinationRepeater')
        return attempt

    def allowed_to_forward(self, case):
        allowed = super().allowed_to_forward(case)
        if allowed:
            return (
                bool(case.get_case_property('cowin_beneficiary_reference_id'))
                and case.get_case_property('api') == COWIN_API_DATA_VACCINATION_IDENTIFIER
            )
        return allowed
