from django.utils.translation import ugettext_lazy as _

from memoized import memoized

from casexml.apps.case.xform import extract_case_blocks
from couchforms.signals import successful_form_received
from dimagi.ext.couchdbkit import StringProperty

from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.data_dictionary.models import CaseType
from corehq.form_processor.interfaces.dbaccessors import (
    CaseAccessors,
    FormAccessors,
)
from corehq.motech.repeater_helpers import RepeaterResponse
from corehq.motech.repeaters.models import CaseRepeater
from corehq.motech.repeaters.repeater_generators import (
    FormDictPayloadGenerator,
)
from corehq.motech.repeaters.signals import create_repeat_records
from corehq.motech.utils import pformat_json
from corehq.motech.value_source import (
    CaseTriggerInfo,
    get_form_question_values,
)
from corehq.privileges import DATA_FORWARDING
from corehq.toggles import FHIR_INTEGRATION

from .const import FHIR_VERSION_4_0_1, XMLNS_FHIR
from .repeater_helpers import (
    get_info_resources_list,
    register_patients,
    send_resources,
)


class FHIRRepeater(CaseRepeater):
    class Meta:
        app_label = 'repeaters'

    friendly_name = _('Forward Cases to a FHIR API')
    payload_generator_classes = (FormDictPayloadGenerator,)
    include_app_id_param = False
    _has_config = False

    fhir_version = StringProperty(default=FHIR_VERSION_4_0_1)

    @memoized
    def payload_doc(self, repeat_record):
        return FormAccessors(repeat_record.domain).get_form(repeat_record.payload_id)

    @property
    def form_class_name(self):
        # The class name used to determine which edit form to use
        return self.__class__.__name__

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
        case_trigger_infos = self.get_case_trigger_infos(payload)
        try:
            resources = get_info_resources_list(
                case_trigger_infos,
                self.fhir_version,
            )
            if not resources:
                # Nothing to send
                return True
            register_patients(requests, resources)
            response = send_resources(requests, resources, self.fhir_version)
        except Exception as err:
            requests.notify_exception(str(err))
            return RepeaterResponse(400, 'Bad Request', pformat_json(str(err)))
        return response

    def get_case_trigger_infos(self, form_json):
        case_trigger_infos = []
        case_blocks = extract_case_blocks(form_json)
        case_ids = [case_block['@case_id'] for case_block in case_blocks]
        cases = CaseAccessors(self.domain).get_cases(case_ids, ordered=True)
        for case, case_block in zip(cases, case_blocks):
            assert case_block['@case_id'] == case.case_id
            case_type = CaseType.objects.get(domain=case.domain, name=case.type)
            prop_names = [p.name for p in case_type.properties.all()]
            case_create = case_block.get('create') or {}
            case_update = case_block.get('update') or {}
            case_trigger_infos.append(CaseTriggerInfo(
                domain=self.domain,
                case_id=case.case_id,
                type=case.type,
                name=case.name,
                owner_id=case.owner_id,
                modified_by=case.modified_by,
                updates={**case_create, **case_update},
                created='create' in case_block,
                closed='close' in case_block,
                extra_fields={p: case.get_case_property(p) for p in prop_names},
                form_question_values=get_form_question_values(form_json),
            ))
        return case_trigger_infos


def create_fhir_repeat_records(sender, xform, **kwargs):
    create_repeat_records(FHIRRepeater, xform)


successful_form_received.connect(create_fhir_repeat_records)
