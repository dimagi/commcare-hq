from __future__ import absolute_import
from __future__ import unicode_literals
import json

from couchdbkit.ext.django.schema import SchemaProperty, StringProperty, DateTimeProperty, BooleanProperty
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse

from casexml.apps.case.xform import extract_case_blocks
from corehq.motech.repeaters.models import CaseRepeater
from corehq.motech.repeaters.repeater_generators import FormRepeaterJsonPayloadGenerator
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors
from corehq.toggles import OPENMRS_INTEGRATION
from corehq.motech.repeaters.signals import create_repeat_records
from couchforms.signals import successful_form_received
from corehq.motech.openmrs.const import XMLNS_OPENMRS
from corehq.motech.openmrs.openmrs_config import OpenmrsConfig
from corehq.motech.openmrs.handler import send_openmrs_data
from corehq.motech.openmrs.repeater_helpers import (
    get_relevant_case_updates_from_form_json,
    get_case_location_ancestor_repeaters,
)
from corehq.motech.requests import Requests
from corehq.motech.value_source import get_form_question_values
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

    # self.white_listed_case_types must have exactly one case type set
    # for Atom feed integration to add cases for OpenMRS patients.
    # self.location_id must be set to determine their case owner. The
    # owner is set to the first CommCareUser instance found at that
    # location.
    atom_feed_enabled = BooleanProperty(default=False)
    atom_feed_last_polled_at = DateTimeProperty(default=None)
    atom_feed_last_page = StringProperty(default=None)

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

    def allowed_to_forward(self, payload):
        """
        Forward the payload if ...

        * it did not come from OpenMRS, and
        * CaseRepeater says it's OK for the case types and users of any
          of the payload's cases, and
        * this repeater forwards to the right OpenMRS server for any of
          the payload's cases.

        :param payload: An XFormInstance (not a case)

        """
        if payload.xmlns == XMLNS_OPENMRS:
            # payload came from OpenMRS. Don't send it back.
            return False

        case_blocks = extract_case_blocks(payload)
        case_ids = [case_block['@case_id'] for case_block in case_blocks]
        cases = CaseAccessors(payload.domain).get_cases(case_ids, ordered=True)
        if not any(CaseRepeater.allowed_to_forward(self, case) for case in cases):
            # If none of the case updates in the payload are allowed to
            # be forwarded, drop it.
            return False

        repeaters = [repeater for case in cases for repeater in get_case_location_ancestor_repeaters(case)]
        if repeaters and self not in repeaters:
            # This repeater points to the wrong OpenMRS server for this
            # payload. Let the right repeater handle it.
            return False

        return True

    def get_payload(self, repeat_record):
        payload = super(OpenmrsRepeater, self).get_payload(repeat_record)
        return json.loads(payload)

    def send_request(self, repeat_record, payload):
        case_trigger_infos = get_relevant_case_updates_from_form_json(
            self.domain, payload, case_types=self.white_listed_case_types,
            extra_fields=[identifier.case_property
                          for identifier in self.openmrs_config.case_config.patient_identifiers.values()])
        form_question_values = get_form_question_values(payload)

        return send_openmrs_data(
            Requests(self.domain, self.url, self.username, self.plaintext_password, verify=self.verify),
            self.domain,
            payload,
            self.openmrs_config,
            case_trigger_infos,
            form_question_values
        )


def create_openmrs_repeat_records(sender, xform, **kwargs):
    create_repeat_records(OpenmrsRepeater, xform)


successful_form_received.connect(create_openmrs_repeat_records)
