import json
from couchdbkit.ext.django.schema import *

from django.utils.translation import ugettext_lazy as _
from django.urls import reverse

from corehq.motech.repeaters.models import CaseRepeater
from corehq.motech.repeaters.repeater_generators import FormRepeaterJsonPayloadGenerator
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.toggles import OPENMRS_INTEGRATION
from corehq.motech.repeaters.signals import create_repeat_records
from couchforms.signals import successful_form_received
from custom.infomovel_fgh.openmrs.field_mappings import IdMatcher, OpenmrsConfig
from custom.infomovel_fgh.openmrs.handler import send_openmrs_data
from custom.infomovel_fgh.openmrs.repeater_helpers import get_relevant_case_updates_from_form_json, \
    Requests
from dimagi.utils.decorators.memoized import memoized


# it actually triggers on forms,
# but I wanted to get a case type, and this is the easiest way
class OpenmrsRepeater(CaseRepeater):
    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward to OpenMRS")
    payload_generator_classes = (FormRepeaterJsonPayloadGenerator,)

    openmrs_config = SchemaProperty(OpenmrsConfig)

    @memoized
    def payload_doc(self, repeat_record):
        return FormAccessors(repeat_record.domain).get_form(repeat_record.payload_id)

    @classmethod
    def available_for_domain(cls, domain):
        return OPENMRS_INTEGRATION.enabled(domain)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.infomovel_fgh.openmrs.views import OpenmrsRepeaterView
        return reverse(OpenmrsRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, case):
        return True

    def fire_for_record(self, repeat_record):
        form_json = json.loads(self.get_payload(repeat_record))

        trigger_case_infos = get_relevant_case_updates_from_form_json(
            self.domain, form_json, case_types=self.white_listed_case_types,
            extra_fields=[id_matcher.case_property
                          for id_matcher in self.openmrs_config.case_config.id_matchers])

        send_openmrs_data(Requests(self.url, self.username, self.password), form_json,
                          trigger_case_infos, self.openmrs_config)

        return repeat_record.handle_success(None)


def create_openmrs_repeat_records(sender, xform, **kwargs):
    create_repeat_records(OpenmrsRepeater, xform)


successful_form_received.connect(create_openmrs_repeat_records)
