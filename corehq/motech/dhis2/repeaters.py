import json

from django.utils.translation import ugettext_lazy as _

from couchdbkit import BadValueError
from memoized import memoized
from packaging.version import InvalidVersion, Version
from requests import RequestException
from urllib3.exceptions import HTTPError

from couchforms.signals import successful_form_received
from dimagi.ext.couchdbkit import SchemaProperty, StringProperty

from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.motech.dhis2.const import DHIS2_MAX_VERSION
from corehq.motech.dhis2.dhis2_config import Dhis2Config
from corehq.motech.dhis2.events_helpers import send_dhis2_event
from corehq.motech.repeaters.models import FormRepeater, Repeater
from corehq.motech.repeaters.repeater_generators import (
    FormRepeaterJsonPayloadGenerator,
)
from corehq.motech.repeaters.signals import create_repeat_records
from corehq.motech.requests import Requests
from corehq.toggles import DHIS2_INTEGRATION


def is_dhis2_version(value):
    try:
        version = Version(value)
        major, minor, *the_rest = version.release
        if version > Version(DHIS2_MAX_VERSION):
            raise BadValueError(_(
                f"Versions of DHIS2 higher than {DHIS2_MAX_VERSION} are not "
                "yet supported."
            ))
        if major == 2:
            return True
    except (InvalidVersion, TypeError, ValueError):
        pass
    raise BadValueError(_(
        'DHIS2 version must be in the format "2.xy" or "2.xy.z".'
    ))


def is_dhis2_version_or_blank(value):
    if value is None or value == "":
        return True
    return is_dhis2_version(value)


class Dhis2Repeater(FormRepeater):
    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward Forms to DHIS2 as Anonymous Events")
    payload_generator_classes = (FormRepeaterJsonPayloadGenerator,)

    dhis2_version = StringProperty(validators=[is_dhis2_version_or_blank])
    dhis2_config = SchemaProperty(Dhis2Config)

    _has_config = True

    def __str__(self):
        return Repeater.__str__(self)

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

    @property
    def api_version(self) -> int:
        """
        Check API version to determine what calls/schema are supported
        by the remote system.

        e.g. Not all CRUD operations are supported before version 15.
        """
        if self.dhis2_version:
            major, minor, *the_rest = Version(self.dhis2_version).release
            return minor

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
            notify_addresses=self.notify_addresses,
        )
        for form_config in self.dhis2_config.form_configs:
            if form_config.xmlns == payload['form']['@xmlns']:
                try:
                    return send_dhis2_event(
                        requests,
                        form_config,
                        payload,
                    )
                except (RequestException, HTTPError) as err:
                    requests.notify_error(f"Error sending Events to {self}: {err}")
                    raise
        return True


def create_dhis_repeat_records(sender, xform, **kwargs):
    create_repeat_records(Dhis2Repeater, xform)


successful_form_received.connect(create_dhis_repeat_records)
