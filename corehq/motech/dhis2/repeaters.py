import json
import re

from django.utils.translation import ugettext_lazy as _

from couchdbkit import BadValueError
from memoized import memoized

from couchforms.signals import successful_form_received
from dimagi.ext.couchdbkit import SchemaProperty

from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.motech.dhis2.dhis2_config import Dhis2Config
from corehq.motech.dhis2.events_helpers import send_dhis2_event
from corehq.motech.repeaters.models import FormRepeater
from corehq.motech.repeaters.repeater_generators import (
    FormRepeaterJsonPayloadGenerator,
)
from corehq.motech.repeaters.signals import create_repeat_records
from corehq.motech.requests import Requests
from corehq.toggles import DHIS2_INTEGRATION


def is_dhis2_version(value):
    if re.match(r'^2\.\d+(\.\d)?$', value):
        return True
    raise BadValueError(_('Value must be a DHIS2 version in the format "2.xy" '
                          'or "2.xy.z".'))


def is_dhis2_version_or_blank(value):
    if value is None or value == "":
        return True
    try:
        return is_dhis2_version(value)
    except BadValueError:
        raise BadValueError(_('Value must be a DHIS2 version in the format '
                              '"2.xy" or "2.xy.z", or blank.'))


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


def create_dhis_repeat_records(sender, xform, **kwargs):
    create_repeat_records(Dhis2Repeater, xform)


successful_form_received.connect(create_dhis_repeat_records)
