from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _

from corehq import toggles
from corehq.apps.cowin.repeater_generators import (
    BeneficiaryRegistrationPayloadGenerator,
    BeneficiaryVaccinationPayloadGenerator,
)
from corehq.apps.hqcase.utils import update_case
from corehq.form_processor.signals import sql_case_post_save
from corehq.motech.repeaters.models import CreateCaseRepeater
from corehq.motech.repeaters.signals import create_repeat_records


class BaseCOWINRepeater(CreateCaseRepeater):
    class Meta:
        app_label = 'repeaters'

    @classmethod
    def available_for_domain(cls, domain):
        return toggles.COWIN_INTEGRATION.enabled(domain)

    def get_headers(self, repeat_record):
        headers = super(BaseCOWINRepeater, self).get_headers(repeat_record)
        headers.update({
            'Accept-Language': 'en_US',
            'User-Agent': '',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })
        return headers


class BeneficiaryRegistrationRepeater(BaseCOWINRepeater):
    payload_generator_classes = (BeneficiaryRegistrationPayloadGenerator,)
    friendly_name = _("Register beneficiaries on COWIN")

    def handle_response(self, response, repeat_record):
        attempt = super().handle_response(response, repeat_record)
        if response.status_code == 200:
            beneficiary_reference_id = response.json()['beneficiary_reference_id']
            update_case(self.domain, repeat_record.payload_id, case_properties={
                'cowin_id': beneficiary_reference_id
            })
        return attempt


class BeneficiaryVaccinationRepeater(BaseCOWINRepeater):
    payload_generator_classes = (BeneficiaryVaccinationPayloadGenerator,)
    friendly_name = _("Update vaccination for beneficiaries on COWIN")


@receiver([sql_case_post_save])
def create_cowin_repeat_records(sender, case, **kwargs):
    create_repeat_records(BeneficiaryRegistrationRepeater, case)
    create_repeat_records(BeneficiaryVaccinationRepeater, case)
