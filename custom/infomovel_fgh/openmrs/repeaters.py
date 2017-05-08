from django.utils.translation import ugettext_lazy as _
from django.urls import reverse

from corehq.motech.repeaters.models import CaseRepeater
from corehq.form_processor.models import CommCareCaseSQL
from corehq.toggles import OPENMRS_INTEGRATION
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.motech.repeaters.signals import create_repeat_records


class BaseOpenmrsRepeater(CaseRepeater):
    pass


class RegisterOpenmrsPatientRepeater(BaseOpenmrsRepeater):
    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward CommCare Patients to OpenMRS")

    @classmethod
    def available_for_domain(cls, domain):
        return OPENMRS_INTEGRATION.enabled(domain)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.infomovel_fgh.openmrs.views import RegisterOpenmrsPatientRepeaterView
        return reverse(RegisterOpenmrsPatientRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, case):
        super(RegisterOpenmrsPatientRepeater, self).allowed_to_forward(case)


def create_case_repeat_records(sender, case, **kwargs):
    create_repeat_records(RegisterOpenmrsPatientRepeater, case)


case_post_save.connect(create_case_repeat_records, CommCareCaseSQL)
case_post_save.connect(create_case_repeat_records, CommCareCase)
