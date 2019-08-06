from __future__ import absolute_import
from __future__ import unicode_literals

import json

from dimagi.ext.couchdbkit import SchemaProperty
from memoized import memoized

from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.motech.dhis2.dhis2_config import Dhis2Config
from corehq.motech.repeaters.models import FormRepeater
from corehq.motech.repeaters.repeater_generators import FormRepeaterJsonPayloadGenerator
from corehq.motech.repeaters.signals import create_repeat_records
from couchforms.signals import successful_form_received
from django.utils.translation import ugettext_lazy as _

from corehq.motech.repeaters.views.repeaters import AddDhis2RepeaterView
from corehq.motech.requests import Requests
from corehq.motech.dhis2.handler import send_data_to_dhis2
from corehq.toggles import DHIS2_INTEGRATION
from corehq.util import reverse


class Dhis2Repeater(FormRepeater):
    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward Forms to DHIS2 as Anonymous Events")
    payload_generator_classes = (FormRepeaterJsonPayloadGenerator,)

    dhis2_config = SchemaProperty(Dhis2Config)

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__) and
            self.get_id == other.get_id
        )

    def __ne__(self, other):
        return not self.__eq__(other)

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

    @classmethod
    def get_custom_url(cls, domain):
        return reverse(AddDhis2RepeaterView.urlname, args=[domain])

    def get_payload(self, repeat_record):
        payload = super(Dhis2Repeater, self).get_payload(repeat_record)
        return json.loads(payload)

    def send_request(self, repeat_record, payload):
        for form_config in self.dhis2_config.form_configs:
            if form_config.xmlns == payload['form']['@xmlns']:
                return send_data_to_dhis2(
                    Requests(self.domain, self.url, self.username, self.plaintext_password, verify=self.verify),
                    form_config,
                    payload,
                )


def create_dhis_repeat_records(sender, xform, **kwargs):
    create_repeat_records(Dhis2Repeater, xform)


successful_form_received.connect(create_dhis_repeat_records)
