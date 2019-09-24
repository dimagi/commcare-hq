import json

from django.utils.translation import ugettext_lazy as _

from memoized import memoized

from couchforms.signals import successful_form_received
from dimagi.ext.couchdbkit import SchemaProperty

from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.motech.dhis2.dhis2_config import Dhis2Config, Dhis2EntityConfig
from corehq.motech.dhis2.events_helpers import send_dhis2_event
from corehq.motech.dhis2.entities_helpers import send_dhis2_entities
from corehq.motech.repeater_helpers import (
    get_relevant_case_updates_from_form_json,
)
from corehq.motech.repeaters.models import CaseRepeater, FormRepeater
from corehq.motech.repeaters.repeater_generators import (
    FormRepeaterJsonPayloadGenerator,
)
from corehq.motech.repeaters.signals import create_repeat_records
from corehq.motech.requests import Requests
from corehq.motech.value_source import get_form_question_values
from corehq.toggles import DHIS2_INTEGRATION


class Dhis2EntityRepeater(CaseRepeater):
    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward Cases as DHIS2 Tracked Entities")
    payload_generator_classes = (FormRepeaterJsonPayloadGenerator,)

    dhis2_entity_config = SchemaProperty(Dhis2EntityConfig)

    _has_config = True

    def __str__(self):
        return f'Forwarding cases to "{self.url}" as DHIS2 Tracked Entity instances'

    def allowed_to_forward(self, payload):
        return True

    @memoized
    def payload_doc(self, repeat_record):
        return FormAccessors(repeat_record.domain).get_form(repeat_record.payload_id)

    @property
    def form_class_name(self):
        return self.__class__.__name__

    @classmethod
    def available_for_domain(cls, domain):
        return DHIS2_INTEGRATION.enabled(domain)

    def get_payload(self, repeat_record):
        payload = super().get_payload(repeat_record)
        return json.loads(payload)

    def send_request(self, repeat_record, payload):
        value_sources = []
        for case_config in self.dhis2_entity_config.case_configs:
            value_sources.append(case_config.org_unit_id)
            for value_source in case_config.attributes.values():
                value_sources.append(value_source)

        case_trigger_infos = get_relevant_case_updates_from_form_json(
            self.domain, payload, case_types=self.white_listed_case_types,
            extra_fields=[vs.case_property for vs in value_sources if hasattr(vs, 'case_property')],
            form_question_values=get_form_question_values(payload),
        )
        requests = Requests(
            self.domain,
            self.url,
            self.username,
            self.plaintext_password,
            verify=self.verify,
        )
        return send_dhis2_entities(
            requests,
            payload,
            self.dhis2_entity_config,
            case_trigger_infos,
        )


class Dhis2Repeater(FormRepeater):
    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward Forms to DHIS2 as Anonymous Events")
    payload_generator_classes = (FormRepeaterJsonPayloadGenerator,)

    dhis2_config = SchemaProperty(Dhis2Config)

    _has_config = True

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__) and
            self.get_id == other.get_id
        )

    def __hash__(self):
        return hash(self.get_id)

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
        return DHIS2_INTEGRATION.enabled(domain)

    def get_payload(self, repeat_record):
        payload = super(Dhis2Repeater, self).get_payload(repeat_record)
        return json.loads(payload)

    def send_request(self, repeat_record, payload):
        """
        Sends API request and returns response if ``payload`` is a form
        that is configured to be forwarded to DHIS2.

        If ``payload`` is a form that isn't configured to be forwarded,
        returns True.
        """
        requests = Requests(
            self.domain,
            self.url,
            self.username,
            self.plaintext_password,
            verify=self.verify,
        )
        for form_config in self.dhis2_config.form_configs:
            if form_config.xmlns == payload['form']['@xmlns']:
                return send_dhis2_event(
                    requests,
                    form_config,
                    payload,
                )
        return True


def create_dhis2_event_repeat_records(sender, xform, **kwargs):
    create_repeat_records(Dhis2Repeater, xform)


def create_dhis2_entity_repeat_records(sender, xform, **kwargs):
    create_repeat_records(Dhis2EntityRepeater, xform)


successful_form_received.connect(create_dhis2_event_repeat_records)
successful_form_received.connect(create_dhis2_entity_repeat_records)
