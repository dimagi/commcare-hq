from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _

from corehq import toggles
from corehq.apps.cowin.repeater_generators import (
    BeneficiaryRegistrationPayloadGenerator,
    BeneficiaryVaccinationPayloadGenerator,
)
from corehq.apps.hqcase.utils import update_case
from corehq.form_processor.models import CommCareCaseSQL
from corehq.apps.cowin.api import API_KEYS
from corehq.motech.repeaters.models import CaseRepeater
from corehq.motech.repeaters.signals import create_repeat_records

from casexml.apps.case.signals import case_post_save


class BaseCOWINRepeater(CaseRepeater):
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

    def get_headers(self, repeat_record):
        headers = super(BeneficiaryRegistrationRepeater, self).get_headers(repeat_record)
        headers.update({
            'X-Api-Key': API_KEYS['vaccinator'],
        })
        return headers

    def handle_response(self, response, repeat_record):
        attempt = super().handle_response(response, repeat_record)
        if response.status_code == 200:
            beneficiary_reference_id = response.json()['beneficiary_reference_id']
            update_case(self.domain, repeat_record.payload_id, case_properties={
                'cowin_id': beneficiary_reference_id
            })
        return attempt

    def allowed_to_forward(self, case):
        allowed = super().allowed_to_forward(case)
        if allowed:
            return not bool(case.get_case_property('cowin_id'))
        return allowed


class BeneficiaryVaccinationRepeater(BaseCOWINRepeater):
    payload_generator_classes = (BeneficiaryVaccinationPayloadGenerator,)
    friendly_name = _("Update vaccination for beneficiaries on COWIN")

    def get_headers(self, repeat_record):
        headers = super(BeneficiaryVaccinationRepeater, self).get_headers(repeat_record)
        headers.update({
            'X-Api-Key': API_KEYS['vaccinator'],
        })
        return headers

    def allowed_to_forward(self, case):
        allowed = super().allowed_to_forward(case)
        if allowed:
            return bool(case.get_case_property('cowin_id'))
        return allowed


def create_cowin_repeat_records(sender, case, **kwargs):
    create_repeat_records(BeneficiaryRegistrationRepeater, case)
    create_repeat_records(BeneficiaryVaccinationRepeater, case)


case_post_save.connect(create_cowin_repeat_records, CommCareCaseSQL)
