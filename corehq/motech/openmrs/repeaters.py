from __future__ import absolute_import
from __future__ import unicode_literals
import json
from collections import defaultdict

import six
from itertools import chain

from corehq.motech.openmrs.handler import (
    CreateVisitsEncountersObsTask,
    SyncPatientIdentifiersTask,
    SyncPersonAttributesTask,
)
from corehq.motech.openmrs.logger import logger
from corehq.motech.openmrs.workflow import execute_workflow
from corehq.motech.utils import pformat_json

from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DateTimeProperty,
    DocumentSchema,
    SchemaDictProperty,
    SchemaProperty,
    StringProperty,
)
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse

from corehq.motech.const import DIRECTION_IMPORT
from casexml.apps.case.xform import extract_case_blocks
from corehq.motech.repeaters.models import CaseRepeater
from corehq.motech.repeaters.repeater_generators import FormRepeaterJsonPayloadGenerator
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors
from corehq.toggles import OPENMRS_INTEGRATION
from corehq.motech.repeaters.signals import create_repeat_records
from couchforms.signals import successful_form_received
from corehq.motech.openmrs.const import XMLNS_OPENMRS, ATOM_FEED_NAME_PATIENT
from corehq.motech.openmrs.openmrs_config import OpenmrsConfig
from corehq.motech.openmrs.repeater_helpers import (
    get_relevant_case_updates_from_form_json,
    get_case_location_ancestor_repeaters,
    get_patient,
    UpdatePersonNameTask,
    UpdatePersonPropertiesTask,
    UpdatePersonAddressTask,
    CreatePersonAddressTask,
    OpenmrsResponse,
)
from corehq.motech.requests import Requests
from corehq.motech.value_source import get_form_question_values, CaseTriggerInfo
from memoized import memoized


class AtomFeedStatus(DocumentSchema):
    last_polled_at = DateTimeProperty(default=None)
    last_page = StringProperty(default=None)


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
    atom_feed_status = SchemaDictProperty(AtomFeedStatus)

    def __init__(self, *args, **kwargs):
        super(OpenmrsRepeater, self).__init__(*args, **kwargs)

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__) and
            self.get_id == other.get_id
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    @classmethod
    def wrap(cls, data):
        if 'atom_feed_last_polled_at' in data:
            data['atom_feed_status'] = {
                ATOM_FEED_NAME_PATIENT: {
                    'last_polled_at': data.pop('atom_feed_last_polled_at'),
                    'last_page': data.pop('atom_feed_last_page', None),
                }
            }
        return super(OpenmrsRepeater, cls).wrap(data)

    @cached_property
    def requests(self):
        return Requests(
            self.domain,
            self.url,
            self.username,
            self.plaintext_password,
            verify=self.verify
        )

    @cached_property
    def observation_mappings(self):
        obs_mappings = defaultdict(list)
        for form_config in self.openmrs_config.form_configs:
            for obs_mapping in form_config.openmrs_observations:
                if obs_mapping.value.check_direction(DIRECTION_IMPORT) and obs_mapping.case_property:
                    obs_mappings[obs_mapping.concept].append(obs_mapping)
        return obs_mappings

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
        value_sources = chain(
            six.itervalues(self.openmrs_config.case_config.patient_identifiers),
            six.itervalues(self.openmrs_config.case_config.person_properties),
            six.itervalues(self.openmrs_config.case_config.person_preferred_name),
            six.itervalues(self.openmrs_config.case_config.person_preferred_address),
            six.itervalues(self.openmrs_config.case_config.person_attributes),
        )
        case_trigger_infos = get_relevant_case_updates_from_form_json(
            self.domain, payload, case_types=self.white_listed_case_types,
            extra_fields=[vs.case_property for vs in value_sources if hasattr(vs, 'case_property')]
        )
        form_question_values = get_form_question_values(payload)

        return send_openmrs_data(
            self.requests,
            self.domain,
            payload,
            self.openmrs_config,
            case_trigger_infos,
            form_question_values
        )


def send_openmrs_data(requests, domain, form_json, openmrs_config, case_trigger_infos, form_question_values):
    """
    Updates an OpenMRS patient and (optionally) creates visits.

    This involves several requests to the `OpenMRS REST Web Services`_. If any of those requests fail, we want to
    roll back previous changes to avoid inconsistencies in OpenMRS. To do this we define a workflow of tasks we
    want to do. Each workflow task has a rollback task. If a task fails, all previous tasks are rolled back in
    reverse order.

    :return: A response-like object that can be used by Repeater.handle_response


    .. _OpenMRS REST Web Services: https://wiki.openmrs.org/display/docs/REST+Web+Services+API+For+Clients
    """
    errors = []
    for info in case_trigger_infos:
        assert isinstance(info, CaseTriggerInfo)
        patient = get_patient(requests, domain, info, openmrs_config)
        if patient is None:
            errors.append('Warning: CommCare case "{}" was not found in OpenMRS'.format(info.case_id))
            continue

        # case_trigger_infos are info about all of the cases
        # created/updated by the form. Execute a separate workflow to
        # update each patient.
        workflow = [
            # Update name first. If the current name in OpenMRS fails
            # validation, other API requests will be rejected.
            UpdatePersonNameTask(requests, info, openmrs_config, patient['person']),
            # Update identifiers second. If a current identifier fails
            # validation, other API requests will be rejected.
            SyncPatientIdentifiersTask(requests, info, openmrs_config, patient),
            # Now we should be able to update the rest.
            UpdatePersonPropertiesTask(requests, info, openmrs_config, patient['person']),
            SyncPersonAttributesTask(
                requests, info, openmrs_config, patient['person']['uuid'], patient['person']['attributes']
            ),
        ]
        if patient['person']['preferredAddress']:
            workflow.append(
                UpdatePersonAddressTask(requests, info, openmrs_config, patient['person'])
            )
        else:
            workflow.append(
                CreatePersonAddressTask(requests, info, openmrs_config, patient['person'])
            )
        workflow.append(
            CreateVisitsEncountersObsTask(
                requests, domain, info, form_json, form_question_values, openmrs_config, patient['person']['uuid']
            ),
        )

        errors.extend(
            execute_workflow(workflow)
        )

    if errors:
        logger.error('Errors encountered sending OpenMRS data: %s', errors)
        # If the form included multiple patients, some workflows may
        # have succeeded, but don't say everything was OK if any
        # workflows failed. (Of course most forms will only involve one
        # case, so one workflow.)
        return OpenmrsResponse(400, 'Bad Request', pformat_json([str(e) for e in errors]))
    else:
        return OpenmrsResponse(200, 'OK', '')


def create_openmrs_repeat_records(sender, xform, **kwargs):
    create_repeat_records(OpenmrsRepeater, xform)


successful_form_received.connect(create_openmrs_repeat_records)
