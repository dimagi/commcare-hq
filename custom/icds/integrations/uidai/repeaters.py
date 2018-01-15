from __future__ import absolute_import
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse
from django.conf import settings

from corehq.motech.repeaters.models import CaseRepeater
from corehq.toggles import AADHAAR_DEMO_AUTH_INTEGRATION
from custom.enikshay.integrations.utils import case_properties_changed
from custom.icds.const import AADHAAR_NUMBER_CASE_PROPERTY
from custom.icds.integrations.uidai.repeater_generator import AadhaarDemoAuthRepeaterGenerator
from aadhaar_demo_auth.authenticate import AuthenticateAadhaarDemographicDetails


class AadhaarDemoAuthRepeater(CaseRepeater):
    @classmethod
    def available_for_domain(cls, domain):
        return AADHAAR_DEMO_AUTH_INTEGRATION.enabled(domain)

    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("validate cases by aadhaar demo auth")

    payload_generator_classes = (AadhaarDemoAuthRepeaterGenerator,)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.icds.integrations.uidai.views import AadhaarDemoAuthRepeaterView
        return reverse(AadhaarDemoAuthRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, person_case):
        allowed_case_types_and_users = self._allowed_case_type(person_case) and self._allowed_user(person_case)
        if allowed_case_types_and_users:
            return (
                person_case.get_case_property(AADHAAR_NUMBER_CASE_PROPERTY) and
                case_properties_changed(person_case, [AADHAAR_NUMBER_CASE_PROPERTY])
            )

    def fire_for_record(self, repeat_record):
        try:
            payload = self.get_payload(repeat_record)
            person_matches = AuthenticateAadhaarDemographicDetails(
                payload['aadhaar_number'],
                {"Pi":
                    {"name": payload.get('name'),
                     "gender": payload.get('gender'),
                     "dob": payload.get('dob'),
                     }
                 },
                {
                    'ip': payload.get('ip'),
                    'unique_id': payload.get('device_id'),
                 },
                config_file_path=settings.AADHAAR_AUTH_CONFIG_FILE_PATH
            ).authenticate()
            repeat_record.handle_success(None)
            return self.generator.handle_success(
                person_matches,
                self.payload_doc(repeat_record),
                repeat_record)
        except Exception as e:
            return repeat_record.handle_exception(e)
