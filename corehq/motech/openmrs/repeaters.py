from __future__ import absolute_import
from __future__ import unicode_literals
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
from corehq.motech.openmrs.openmrs_config import OpenmrsConfig
from corehq.motech.openmrs.handler import send_openmrs_data
from corehq.motech.openmrs.repeater_helpers import (
    Requests,
    get_form_question_values,
    get_relevant_case_updates_from_form_json,
)
from memoized import memoized


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

    @property
    def form_class_name(self):
        """
        The class name used to determine which edit form to use
        """
        return self.__class__.__name__

    @classmethod
    def available_for_domain(cls, domain):
        return OPENMRS_INTEGRATION.enabled(domain)

    @classmethod
    def get_custom_url(cls, domain):
        from corehq.motech.repeaters.views.repeaters import AddOpenmrsRepeaterView
        return reverse(AddOpenmrsRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, case):
        return True

    def fire_for_record(self, repeat_record):
        form_json = json.loads(self.get_payload(repeat_record))

        case_trigger_infos = get_relevant_case_updates_from_form_json(
            self.domain, form_json, case_types=self.white_listed_case_types,
            extra_fields=[id_matcher.case_property
                          for id_matcher in self.openmrs_config.case_config.id_matchers])
        form_question_values = get_form_question_values(form_json)

        send_openmrs_data(Requests(self.url, self.username, self.password), form_json, self.openmrs_config,
                          case_trigger_infos, form_question_values)

        return repeat_record.handle_success(None)


def create_openmrs_repeat_records(sender, xform, **kwargs):
    create_repeat_records(OpenmrsRepeater, xform)


successful_form_received.connect(create_openmrs_repeat_records)
