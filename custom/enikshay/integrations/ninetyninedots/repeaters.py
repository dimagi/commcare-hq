from corehq.toggles import NINETYNINE_DOTS
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from corehq.apps.repeaters.models import CaseRepeater


class NinetyNineDotsRegisterPatientRepeater(CaseRepeater):
    class Meta(object):
        app_label = 'repeaters'

    friendly_name = _("99DOTS Patient Registration")

    @classmethod
    def available_for_domain(cls, domain):
        return NINETYNINE_DOTS.enabled(domain)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.ninetyninedots.views import RegisterPatientRepeaterView
        return reverse(RegisterPatientRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, case):
        # checks whitelisted case types and users
        allowed_case_types_and_users = super(NinetyNineDotsRegisterPatientRepeater, self).allowed_to_forward(case)
        enabled = case.dynamic_case_properties().get('dots_99_enabled') == 'true'
        not_registered = (
            case.dynamic_case_properties().get('dots_99_registered') == 'false' or
            case.dynamic_case_properties().get('dots_99_registered') is None
        )

        return allowed_case_types_and_users and enabled and not_registered
