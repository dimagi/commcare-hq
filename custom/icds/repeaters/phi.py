from django.utils.translation import ugettext_lazy as _

from corehq import toggles
from corehq.motech.repeaters.models import CaseRepeater
from custom.icds.integrations.phi import send_request
from custom.icds.repeaters.generators.phi import (
    SearchByParamsPayloadGenerator,
    ValidatePHIDPayloadGenerator,
)


class BasePHIRepeater(CaseRepeater):
    @classmethod
    def available_for_domain(cls, domain):
        return toggles.PHI_CAS_INTEGRATION.enabled(domain)


class SearchByParamsRepeater(BasePHIRepeater):
    payload_generator_classes = (SearchByParamsPayloadGenerator,)
    friendly_name = _("Search for Beneficiary via params to get PHI ID")

    def allowed_to_forward(self, payload):
        return (
            super(SearchByParamsRepeater, self).allowed_to_forward(payload) and
            not payload.get_case_property('phid_validated')
        )

    def send_request(self, repeat_record, payload):
        return send_request('search', payload)


class ValidatePHIDRepeater(CaseRepeater):
    payload_generator_classes = (ValidatePHIDPayloadGenerator,)
    friendly_name = _("Validate PHI ID")

    @classmethod
    def available_for_domain(cls, domain):
        return toggles.PHI_CAS_INTEGRATION.enabled(domain)

    def allowed_to_forward(self, payload):
        return (
            super(ValidatePHIDRepeater, self).allowed_to_forward(payload) and
            payload.get_case_property('phid_for_beneficiary')
        )

    def send_request(self, repeat_record, payload):
        return send_request('validate', payload)
