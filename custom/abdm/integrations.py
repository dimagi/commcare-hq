
from abdm_integrator.integrations import HRPIntegration

from corehq.form_processor.models.cases import CommCareCase


class HRPIntegrationHQ(HRPIntegration):

    def check_if_abha_registered(self, user, abha, **kwargs):
        return bool(CommCareCase.objects.get_case_by_external_id(domain=user.domain,
                                                                 external_id=abha))
