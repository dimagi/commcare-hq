import json
import re
import sys
import traceback
from datetime import datetime, timedelta

from django.utils.translation import gettext_lazy as _

from looseversion import LooseVersion
from memoized import memoized
from requests import RequestException
from urllib3.exceptions import HTTPError

from couchforms.signals import successful_form_received

from corehq.form_processor.models import XFormInstance
from corehq.motech.dhis2.const import DHIS2_MAX_KNOWN_GOOD_VERSION, XMLNS_DHIS2
from corehq.motech.dhis2.dhis2_config import Dhis2EntityConfig, Dhis2FormConfig
from corehq.motech.dhis2.entities_helpers import send_dhis2_entities
from corehq.motech.dhis2.events_helpers import send_dhis2_event
from corehq.motech.dhis2.exceptions import Dhis2Exception
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.repeater_helpers import (
    RepeaterResponse,
    get_relevant_case_updates_from_form_json,
)
from corehq.motech.repeaters.models import (
    CaseRepeater,
    FormRepeater,
    OptionValue,
)
from corehq.motech.repeaters.optionvalue import DateTimeCoder
from corehq.motech.repeaters.repeater_generators import (
    FormRepeaterJsonPayloadGenerator,
)
from corehq.motech.repeaters.signals import create_repeat_records
from corehq.motech.value_source import get_form_question_values
from corehq.toggles import DHIS2_INTEGRATION

api_version_re = re.compile(r'^2\.\d+(\.\d)?$')


class Dhis2Instance(object):

    dhis2_version = OptionValue(default=None)
    dhis2_version_last_modified = OptionValue(default=None, coder=DateTimeCoder)

    def get_api_version(self) -> int:
        if (
            self.dhis2_version is None
            or self.dhis2_version_last_modified + timedelta(days=365) < datetime.now()
        ):
            # Fetching DHIS2 metadata is expensive. Only do it if we
            # don't know the version of DHIS2, or if we haven't checked
            # for over a year.
            self.update_dhis2_version()
        return get_api_version(self.dhis2_version)

    def update_dhis2_version(self):
        """
        Fetches metadata from DHIS2 instance and saves DHIS2 version.

        Notifies administrators if the version of DHIS2 exceeds the
        maximum supported version, but still saves and continues.
        """
        requests = self.connection_settings.get_requests(self)
        metadata = fetch_metadata(requests)
        dhis2_version = metadata["system"]["version"]
        try:
            get_api_version(dhis2_version)
        except Dhis2Exception as err:
            requests.notify_exception(str(err))
            raise
        if LooseVersion(dhis2_version) > DHIS2_MAX_KNOWN_GOOD_VERSION:
            requests.notify_error(
                "Integration has not yet been tested for DHIS2 version "
                f"{dhis2_version}. Its API may not be supported."
            )
        self.dhis2_version = dhis2_version
        self.dhis2_version_last_modified = datetime.now()
        self.save()


class Dhis2Repeater(FormRepeater, Dhis2Instance):
    class Meta:
        proxy = True
        app_label = 'repeaters'

    include_app_id_param = False
    dhis2_config = OptionValue(default=dict)

    friendly_name = _("Forward Forms to DHIS2 as Anonymous Events")
    payload_generator_classes = (FormRepeaterJsonPayloadGenerator,)

    _has_config = True

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__)
            and self.id == other.id
        )

    def __hash__(self):
        return hash(self.id)

    def allowed_to_forward(self, payload):
        return (
            super().allowed_to_forward(payload)
            # If the payload is the system form for updating a case with
            # its DHIS2 TEI ID then don't send it back.
            and payload.xmlns != XMLNS_DHIS2
        )

    @memoized
    def payload_doc(self, repeat_record):
        return XFormInstance.objects.get_form(repeat_record.payload_id, repeat_record.domain)

    @property
    def form_class_name(self):
        """
        The class name used to determine which edit form to use
        """
        return 'Dhis2Repeater'

    @classmethod
    def available_for_domain(cls, domain):
        return DHIS2_INTEGRATION.enabled(domain)

    def get_payload(self, repeat_record):
        payload = super().get_payload(repeat_record)
        return json.loads(payload)

    def send_request(self, repeat_record, payload):
        """
        Sends API request and returns response if ``payload`` is a form
        that is configured to be forwarded to DHIS2.

        If ``payload`` is a form that isn't configured to be forwarded,
        returns True.
        """
        # Notify admins if API version is not supported
        self.get_api_version()

        requests = self.connection_settings.get_requests(repeat_record.payload_id)
        for form_config in self.dhis2_config['form_configs']:
            if form_config['xmlns'] == payload['form']['@xmlns']:
                try:
                    return send_dhis2_event(
                        requests,
                        form_config,
                        payload,
                    )
                except (RequestException, HTTPError, ConfigurationError) as err:
                    requests.notify_error(f"Error sending Events to {self}: {err}")
                    raise
        return RepeaterResponse(204, "No content")

    def _validate_dhis2_form_config(self):
        for config in self.dhis2_config.get('form_configs', []):
            Dhis2FormConfig.wrap(config).validate()

    def save(self, *args, **kwargs):
        # ensuring that the valid config is passed while saving
        self._validate_dhis2_form_config()
        super().save(*args, **kwargs)


class Dhis2EntityRepeater(CaseRepeater, Dhis2Instance):
    class Meta():
        proxy = True
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward Cases as DHIS2 Tracked Entities")
    payload_generator_classes = (FormRepeaterJsonPayloadGenerator,)

    dhis2_entity_config = OptionValue(default=dict)

    _has_config = True

    def allowed_to_forward(self, payload):
        # If the payload is the system form for updating a case with its
        # DHIS2 TEI ID then don't send it back.
        return payload.xmlns != XMLNS_DHIS2

    @memoized
    def payload_doc(self, repeat_record):
        return XFormInstance.objects.get_form(repeat_record.payload_id, repeat_record.domain)

    @property
    def form_class_name(self):
        return 'Dhis2EntityRepeater'

    @classmethod
    def available_for_domain(cls, domain):
        return DHIS2_INTEGRATION.enabled(domain)

    def get_payload(self, repeat_record):
        payload = super().get_payload(repeat_record)
        return json.loads(payload)

    def send_request(self, repeat_record, payload):
        # Notify admins if API version is not supported
        self.get_api_version()

        value_source_configs = []
        for case_config in self.dhis2_entity_config['case_configs']:
            value_source_configs.append(case_config['org_unit_id'])
            value_source_configs.append(case_config['tei_id'])
            for value_source_config in case_config['attributes'].values():
                value_source_configs.append(value_source_config)

        case_trigger_infos = get_relevant_case_updates_from_form_json(
            self.domain, payload, case_types=self.white_listed_case_types,
            extra_fields=[c['case_property'] for c in value_source_configs
                          if 'case_property' in c],
            form_question_values=get_form_question_values(payload),
        )
        requests = self.connection_settings.get_requests(repeat_record.payload_id)
        try:
            return send_dhis2_entities(requests, self, case_trigger_infos)
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            requests.notify_error(
                f"Error sending Entities to {self}: {exc_value!r}",
                details="".join(tb_lines)
            )
            raise

    def _validate_dhis2_entity_config(self):
        for config in self.dhis2_entity_config.get('case_configs', []):
            Dhis2EntityConfig.wrap(config).validate()

    def save(self, *args, **kwargs):
        # ensuring that the valid config is passed while saving
        self._validate_dhis2_entity_config()
        super().save(*args, **kwargs)


def get_api_version(dhis2_version):
    """
    Returns the API version supported by the DHIS2 instance.

    `DHIS 2 Developer guide`_:

        The Web API is versioned starting from DHIS 2.25. The API
        versioning follows the DHIS 2 major version numbering. As an
        example, the API version for DHIS 2.25 is 25.


    .. _DHIS 2 Developer guide: https://docs.dhis2.org/master/en/developer/html/webapi_browsing_the_web_api.html#webapi_api_versions
    """  # noqa: E501
    try:
        api_version = LooseVersion(dhis2_version).version[1]
    except (AttributeError, IndexError):
        raise Dhis2Exception(f"Unable to parse DHIS2 version {dhis2_version}.")
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
    response = requests.get('/api/metadata', raise_for_status=True, params={'assumeTrue': 'false'})
    return response.json()


def create_dhis2_event_repeat_records(sender, xform, **kwargs):
    create_repeat_records(Dhis2Repeater, xform)


def create_dhis2_entity_repeat_records(sender, xform, **kwargs):
    create_repeat_records(Dhis2EntityRepeater, xform)


successful_form_received.connect(create_dhis2_event_repeat_records)
successful_form_received.connect(create_dhis2_entity_repeat_records)
