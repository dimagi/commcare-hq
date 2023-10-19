
from abdm_integrator.integrations import HRPIntegration

from corehq.form_processor.models.cases import CommCareCase
from custom.abdm.fhir.document_bundle import fhir_health_data_from_hq


class HRPIntegrationHQ(HRPIntegration):

    def check_if_abha_registered(self, abha, user, **kwargs):
        return bool(CommCareCase.objects.get_case_by_external_id(domain=user.domain,
                                                                 external_id=abha))

    def fetch_health_data(self, care_context_reference, health_info_types, linked_care_context_details, **kwargs):
        domain = linked_care_context_details['additional_info']['domain']
        return fhir_health_data_from_hq(care_context_reference, health_info_types, domain)
