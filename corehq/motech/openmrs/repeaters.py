from __future__ import absolute_import
from __future__ import unicode_literals
import json

from couchdbkit.ext.django.schema import SchemaProperty, StringProperty
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse

from corehq.apps.locations.models import SQLLocation
from corehq.motech.repeaters.models import CaseRepeater
from corehq.motech.repeaters.repeater_generators import FormRepeaterJsonPayloadGenerator
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.toggles import OPENMRS_INTEGRATION
from corehq.motech.repeaters.signals import create_repeat_records
from couchforms.signals import successful_form_received
from corehq.motech.openmrs.const import XMLNS_OPENMRS
from corehq.motech.openmrs.openmrs_config import OpenmrsConfig
from corehq.motech.openmrs.handler import send_openmrs_data
from corehq.motech.openmrs.repeater_helpers import (
    Requests,
    get_form_question_values,
    get_relevant_case_updates_from_form_json,
    get_case_location_ancestor_repeaters,
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

    location_id = StringProperty(default='')
    openmrs_config = SchemaProperty(OpenmrsConfig)

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__) and
            self.get_id == other.get_id
        )

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
        """
        Forward if superclass rules say it's OK, and if the last case
        update did not come from OpenMRS, and if this repeater forwards
        to the right server for this case.
        """
        if not super(OpenmrsRepeater, self).allowed_to_forward(case):
            return False
        last_form = FormAccessors(case.domain).get_form(case.xform_ids[-1])
        if last_form.xmlns == XMLNS_OPENMRS:
            # Case update came from OpenMRS. Don't send it back.
            return False
        repeaters = get_case_location_ancestor_repeaters(case)
        if repeaters and self not in repeaters:
            # self points to the wrong server for this case. Let the right repeater handle it.
            return False
        return True

    def get_payload(self, repeat_record):
        payload = super(OpenmrsRepeater, self).get_payload(repeat_record)
        return json.loads(payload)

    def send_request(self, repeat_record, payload, verify=None):
        case_trigger_infos = get_relevant_case_updates_from_form_json(
            self.domain, payload, case_types=self.white_listed_case_types,
            extra_fields=[identifier.case_property
                          for identifier in self.openmrs_config.case_config.patient_identifiers.values()])
        form_question_values = get_form_question_values(payload)

        return send_openmrs_data(
            Requests(self.url, self.username, self.password),
            self.domain,
            payload,
            self.openmrs_config,
            case_trigger_infos,
            form_question_values
        )


def create_openmrs_repeat_records(sender, xform, **kwargs):
    create_repeat_records(OpenmrsRepeater, xform)


successful_form_received.connect(create_openmrs_repeat_records)
