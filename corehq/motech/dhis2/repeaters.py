import json
from distutils.version import LooseVersion

from django.utils.translation import ugettext_lazy as _

from memoized import memoized
from requests import RequestException
from urllib3.exceptions import HTTPError

from couchforms.signals import successful_form_received
from dimagi.ext.couchdbkit import SchemaProperty, StringProperty

from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.motech.dhis2.const import DHIS2_MAX_VERSION
from corehq.motech.dhis2.dhis2_config import Dhis2Config
from corehq.motech.dhis2.events_helpers import send_dhis2_event
from corehq.motech.dhis2.exceptions import Dhis2Exception
from corehq.motech.repeaters.models import FormRepeater, Repeater
from corehq.motech.repeaters.repeater_generators import (
    FormRepeaterJsonPayloadGenerator,
)
from corehq.motech.repeaters.signals import create_repeat_records
from corehq.motech.requests import Requests
from corehq.toggles import DHIS2_INTEGRATION


class Dhis2Repeater(FormRepeater):
    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward Forms to DHIS2 as Anonymous Events")
    payload_generator_classes = (FormRepeaterJsonPayloadGenerator,)

    dhis2_config = SchemaProperty(Dhis2Config)
    dhis2_version = StringProperty(default=None)

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

    @property
    def api_version(self) -> int:
        """
        Returns the API version supported by the DHIS2 instance.

        `DHIS 2 Developer guide`_:

            The Web API is versioned starting from DHIS 2.25. The API
            versioning follows the DHIS 2 major version numbering. As an
            example, the API version for DHIS 2.25 is 25.


        .. _DHIS 2 Developer guide: https://docs.dhis2.org/master/en/developer/html/webapi_browsing_the_web_api.html#webapi_api_versions
        """
        if self.dhis2_version is None:
            requests = self.get_requests()
            metadata = fetch_metadata(requests)
            self.dhis2_version = metadata["system"]["version"]
            try:
                get_api_version(self.dhis2_version)
            except ValueError as err:
                requests.notify_exception(str(err))
                raise Dhis2Exception from err
            if LooseVersion(self.dhis2_version) > DHIS2_MAX_VERSION:
                requests.notify_error(
                    "Integration has not yet been tested for DHIS2 version "
                    f"{self.dhis2_version}. Its API may not be supported."
                )
            self.save()
        return get_api_version(self.dhis2_version)

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
        requests = self.get_requests()
        for form_config in self.dhis2_config.form_configs:
            if form_config.xmlns == payload['form']['@xmlns']:
                try:
                    return send_dhis2_event(
                        requests,
                        self.api_version,
                        form_config,
                        payload,
                    )
                except (RequestException, HTTPError) as err:
                    requests.notify_error(f"Error sending Events to {self}: {err}")
                    raise
        return True

    def get_requests(self):
        return Requests(
            self.domain,
            self.url,
            self.username,
            self.plaintext_password,
            verify=self.verify,
            notify_addresses=self.notify_addresses,
        )


def get_api_version(dhis2_version):
    try:
        api_version = LooseVersion(dhis2_version).version[1]
    except (AttributeError, IndexError):
        raise ValueError(f"Unable to parse DHIS2 version {dhis2_version}.")
    return api_version


def fetch_metadata(requests):
    """
    Fetch metadata about a DHIS2 instance.

    Currently only used for determining what API version it supports.

    .. NOTE::
       Metadata is large (like a 100MB JSON document), and contains the
       IDs one would need to compile a human-readable configuration into
       one that maps to DHIS2 IDs.

    """
    response = requests.get('/api/metadata', raise_for_status=True)
    return response.json()


def create_dhis_repeat_records(sender, xform, **kwargs):
    create_repeat_records(Dhis2Repeater, xform)


successful_form_received.connect(create_dhis_repeat_records)
