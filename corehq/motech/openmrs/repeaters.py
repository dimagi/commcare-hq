import json
from itertools import chain
from typing import Iterable

from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from jsonobject.containers import JsonDict
from memoized import memoized
from requests import RequestException
from urllib3.exceptions import HTTPError

from casexml.apps.case.xform import extract_case_blocks
from couchforms.signals import successful_form_received
from dimagi.ext.couchdbkit import (
    DateTimeProperty,
    DocumentSchema,
    StringProperty,
)

from corehq.apps.locations.dbaccessors import get_one_commcare_user_at_location
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.motech.openmrs.const import XMLNS_OPENMRS
from corehq.motech.openmrs.openmrs_config import OpenmrsConfig
from corehq.motech.openmrs.repeater_helpers import (
    get_case_location_ancestor_repeaters,
    get_patient,
)
from corehq.motech.openmrs.workflow import execute_workflow
from corehq.motech.openmrs.workflow_tasks import (
    CreatePersonAddressTask,
    CreateVisitsEncountersObsTask,
    SyncPatientIdentifiersTask,
    SyncPersonAttributesTask,
    UpdatePersonAddressTask,
    UpdatePersonNameTask,
    UpdatePersonPropertiesTask,
)
from corehq.motech.repeater_helpers import (
    RepeaterResponse,
    get_relevant_case_updates_from_form_json,
)
from corehq.motech.repeaters.models import OptionValue, CaseRepeater
from corehq.motech.repeaters.repeater_generators import (
    FormRepeaterJsonPayloadGenerator,
)
from corehq.motech.repeaters.signals import create_repeat_records
from corehq.motech.utils import pformat_json
from corehq.motech.value_source import (
    CaseTriggerInfo,
    get_form_question_values,
)
from corehq.toggles import OPENMRS_INTEGRATION


class AtomFeedStatus(DocumentSchema):
    last_polled_at = DateTimeProperty(default=None)

    # The first time the feed is polled, don't replay all the changes
    # since OpenMRS was installed. Start from the most recent changes.
    last_page = StringProperty(default='recent')


class OpenmrsRepeater(CaseRepeater):
    """
    ``OpenmrsRepeater`` is responsible for updating OpenMRS patients
    with changes made to cases in CommCare. It is also responsible for
    creating OpenMRS "visits", "encounters" and "observations" when a
    corresponding visit form is submitted in CommCare.

    The ``OpenmrsRepeater`` class is different from most repeater
    classes in three details:

    1. It has a case type and it updates the OpenMRS equivalent of cases
       like the ``CaseRepeater`` class, but it reads forms like the
       ``FormRepeater`` class. So it subclasses ``CaseRepeater`` but its
       payload format is ``form_json``.

    2. It makes many API calls for each payload.

    3. It can have a location.

    """
    class Meta(object):
        proxy = True
        app_label = 'repeaters'

    friendly_name = _("Forward to OpenMRS")
    payload_generator_classes = (FormRepeaterJsonPayloadGenerator,)

    include_app_id_param = OptionValue(default=False)
    location_id = OptionValue(default='')

    _has_config = True

    # self.white_listed_case_types must have exactly one case type set
    # for Atom feed integration to add cases for OpenMRS patients.
    # self.location_id must be set to determine their case owner. The
    # owner is set to the first CommCareUser instance found at that
    # location.
    atom_feed_enabled = OptionValue(default=False)
    atom_feed_status = OptionValue(default=dict)
    openmrs_config = OptionValue(default=dict)

    @cached_property
    def requests(self):
        # Used by atom_feed module and views that don't have a payload
        # associated with the request
        # TODO: Drop this. Use repeater.connection_settings.get_requests() instead
        return self.connection_settings.get_requests()

    @cached_property
    def first_user(self):
        return get_one_commcare_user_at_location(self.domain, self.location_id)

    @memoized
    def payload_doc(self, repeat_record):
        return XFormInstance.objects.get_form(repeat_record.payload_id, repeat_record.domain)

    @property
    def form_class_name(self):
        """
        The class name used to determine which edit form to use
        """
        return "OpenmrsRepeater"

    @classmethod
    def available_for_domain(cls, domain):
        return OPENMRS_INTEGRATION.enabled(domain)

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
        cases = CommCareCase.objects.get_cases(case_ids, payload.domain, ordered=True)
        if not any(CaseRepeater.allowed_to_forward(self, case) for case in cases):
            # If none of the case updates in the payload are allowed to
            # be forwarded, drop it.
            return False

        if not self.location_id:
            # If this repeater  does not have a location, all payloads
            # should go to it.
            return True

        repeaters = [repeater for case in cases for repeater in get_case_location_ancestor_repeaters(case)]
        # If this repeater points to the wrong OpenMRS server for this
        # payload then let the right repeater handle it.
        return self in repeaters

    def get_payload(self, repeat_record):
        payload = super().get_payload(repeat_record)
        return json.loads(payload)

    def send_request(self, repeat_record, payload):
        value_source_configs: Iterable[JsonDict] = chain(
            self.openmrs_config['case_config']['patient_identifiers'].values(),
            self.openmrs_config['case_config']['person_properties'].values(),
            self.openmrs_config['case_config']['person_preferred_name'].values(),
            self.openmrs_config['case_config']['person_preferred_address'].values(),
            self.openmrs_config['case_config']['person_attributes'].values(),
        )
        case_trigger_infos = get_relevant_case_updates_from_form_json(
            self.domain, payload, case_types=self.white_listed_case_types,
            extra_fields=[conf["case_property"] for conf in value_source_configs if "case_property" in conf],
            form_question_values=get_form_question_values(payload),
        )
        requests = self.connection_settings.get_requests(repeat_record.payload_id)
        try:
            response = send_openmrs_data(
                requests,
                self.domain,
                payload,
                self.openmrs_config,
                case_trigger_infos,
            )
        except Exception as err:
            requests.notify_exception(str(err))
            return RepeaterResponse(400, 'Bad Request', pformat_json(str(err)))
        return response

    def _validate_openmrs_config(self):
        OpenmrsConfig.wrap(self.openmrs_config).validate()
        for feed in self.atom_feed_status.keys():
            AtomFeedStatus.wrap(self.atom_feed_status[feed]).validate()

    def save(self, *args, **kwargs):
        self._validate_openmrs_config()
        super().save(*args, **kwargs)


def send_openmrs_data(requests, domain, form_json, openmrs_config, case_trigger_infos):
    """
    Updates an OpenMRS patient and (optionally) creates visits.

    This involves several requests to the `OpenMRS REST Web Services`_. If any of those requests fail, we want to
    roll back previous changes to avoid inconsistencies in OpenMRS. To do this we define a workflow of tasks we
    want to do. Each workflow task has a rollback task. If a task fails, all previous tasks are rolled back in
    reverse order.

    :return: A response-like object that can be used by Repeater.handle_response(),
             RepeatRecord.handle_success() and RepeatRecord.handle_failure()


    .. _OpenMRS REST Web Services: https://wiki.openmrs.org/display/docs/REST+Web+Services+API+For+Clients
    """
    warnings = []
    errors = []
    for info in case_trigger_infos:
        assert isinstance(info, CaseTriggerInfo)
        try:
            patient = get_patient(requests, domain, info, openmrs_config)
        except (RequestException, HTTPError) as err:
            errors.append(_(
                "Unable to create an OpenMRS patient for case "
                f"{info.case_id!r}: {err}"
            ))
            continue
        if patient is None:
            warnings.append(
                f"CommCare case '{info.case_id}' was not matched to a "
                f"patient in OpenMRS instance '{requests.base_url}'."
            )
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
                requests, domain, info, form_json, openmrs_config, patient['person']['uuid']
            ),
        )

        errors.extend(
            execute_workflow(workflow)
        )

    if errors:
        requests.notify_error(f'Errors encountered sending OpenMRS data: {errors}')
        # If the form included multiple patients, some workflows may
        # have succeeded, but don't say everything was OK if any
        # workflows failed. (Of course most forms will only involve one
        # case, so one workflow.)
        return RepeaterResponse(400, 'Bad Request', "Errors: " + pformat_json([str(e) for e in errors]))

    if warnings:
        return RepeaterResponse(201, "Accepted", "Warnings: " + pformat_json([str(e) for e in warnings]))

    return RepeaterResponse(200, "OK")


def create_openmrs_repeat_records(sender, xform, **kwargs):
    create_repeat_records(OpenmrsRepeater, xform)


successful_form_received.connect(create_openmrs_repeat_records)
