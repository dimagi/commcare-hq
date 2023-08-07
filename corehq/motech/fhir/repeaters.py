from typing import Dict, List, Tuple

from django.utils.translation import gettext_lazy as _

from memoized import memoized

from casexml.apps.case.xform import extract_case_blocks
from couchforms.const import TAG_FORM, TAG_META

from corehq.apps.accounting.utils import domain_has_privilege
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.motech.repeater_helpers import RepeaterResponse
from corehq.motech.repeaters.models import OptionValue, CaseRepeater
from corehq.motech.repeaters.repeater_generators import (
    FormDictPayloadGenerator,
)
from corehq.motech.utils import pformat_json
from corehq.motech.value_source import (
    CaseTriggerInfo,
    get_form_question_values,
)
from corehq.privileges import DATA_FORWARDING
from corehq.toggles import FHIR_INTEGRATION

from .const import FHIR_VERSION_4_0_1, XMLNS_FHIR
from .models import FHIRResourceType, get_case_trigger_info
from .repeater_helpers import (
    get_info_resource_list,
    register_patients,
    send_resources,
)


class FHIRRepeater(CaseRepeater):
    class Meta:
        proxy = True
        app_label = 'repeaters'

    include_app_id_param = False
    fhir_version = OptionValue(default=FHIR_VERSION_4_0_1)
    patient_registration_enabled = OptionValue(default=True)
    patient_search_enabled = OptionValue(default=False)

    friendly_name = _('Forward Cases to a FHIR API')
    payload_generator_classes = (FormDictPayloadGenerator,)
    _has_config = False

    @memoized
    def payload_doc(self, repeat_record):
        return XFormInstance.objects.get_form(repeat_record.payload_id, repeat_record.domain)

    @property
    def form_class_name(self):
        # The class name used to determine which edit form to use
        return "FHIRRepeater"

    @classmethod
    def available_for_domain(cls, domain):
        return (domain_has_privilege(domain, DATA_FORWARDING)
                and FHIR_INTEGRATION.enabled(domain))

    def allowed_to_forward(self, payload):
        # When we update a case's external_id to their ID on a remote
        # FHIR service, the form is submitted with XMLNS_FHIR. This
        # check makes sure that we don't send the update back to FHIR.
        return payload.xmlns != XMLNS_FHIR

    def send_request(self, repeat_record, payload):
        """
        Generates FHIR resources from ``payload``, and sends them as a
        FHIR transaction bundle. If there are patients that need to be
        registered, that is done first.

        Returns an HTTP response-like object. If the payload has nothing
        to send, returns True.
        """
        requests = self.connection_settings.get_requests(repeat_record.payload_id)
        infos, resource_types = self.get_infos_resource_types(
            payload,
            self.fhir_version,
        )
        try:
            resources = get_info_resource_list(infos, resource_types)
            resources = register_patients(
                requests,
                resources,
                self.patient_registration_enabled,
                self.patient_search_enabled,
                self.repeater_id,
            )
            response = send_resources(
                requests,
                resources,
                self.fhir_version,
                self.repeater_id,
            )
        except Exception as err:
            requests.notify_exception(str(err))
            return RepeaterResponse(400, 'Bad Request', pformat_json(str(err)))
        return response

    def get_infos_resource_types(
        self,
        form_json: dict,
        fhir_version: str,
    ) -> Tuple[List[CaseTriggerInfo], Dict[str, FHIRResourceType]]:

        form_question_values = get_form_question_values(form_json)
        case_blocks = extract_case_blocks(form_json)
        cases_by_id = _get_cases_by_id(self.domain, case_blocks)
        resource_types_by_case_type = _get_resource_types_by_case_type(
            self.domain,
            fhir_version,
            cases_by_id.values(),
        )

        case_trigger_info_list = []
        for case_block in case_blocks:
            try:
                case = cases_by_id[case_block['@case_id']]
            except KeyError:
                form_id = form_json[TAG_FORM][TAG_META]['instanceID']
                raise CaseNotFound(
                    f"Form {form_id!r} touches case {case_block['@case_id']!r} "
                    "but that case is not found."
                )
            try:
                resource_type = resource_types_by_case_type[case.type]
            except KeyError:
                # The case type is not mapped to a FHIR resource type.
                # This case is not meant to be represented as a FHIR
                # resource.
                continue
            case_trigger_info_list.append(get_case_trigger_info(
                case,
                resource_type,
                case_block,
                form_question_values,
            ))
        return case_trigger_info_list, resource_types_by_case_type


def _get_cases_by_id(domain, case_blocks):
    case_ids = [case_block['@case_id'] for case_block in case_blocks]
    cases = CommCareCase.objects.get_cases(case_ids, domain, ordered=True)
    return {c.case_id: c for c in cases}


def _get_resource_types_by_case_type(domain, fhir_version, cases):
    case_type_names = {case.type for case in cases}
    fhir_resource_types = (
        FHIRResourceType.objects
        .select_related('case_type')
        .prefetch_related('properties__case_property')
        .filter(
            domain=domain,
            fhir_version=fhir_version,
            case_type__name__in=case_type_names,
        )
    )
    return {rt.case_type.name: rt for rt in fhir_resource_types}
