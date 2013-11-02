from django.utils.translation import ugettext as _
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from custom.fri.models import PROFILE_A, PROFILE_B, PROFILE_C, PROFILE_D, PROFILE_E, PROFILE_F, PROFILE_G, PROFILE_H, PROFILE_DESC
from custom.fri.api import get_interactive_participants

class InteractiveParticipantFilter(BaseSingleOptionFilter):
    slug = "participant"
    label = _("Participant")

    @property
    def options(self):
        cases = get_interactive_participants(self.domain)
        return [(case.get_id, case.name) for case in cases]

class RiskProfileFilter(BaseSingleOptionFilter):
    slug = "risk_profile"
    label = _("Risk Profile")
    default_text = _("All")

    @property
    def options(self):
        return [
            (PROFILE_A, PROFILE_DESC[PROFILE_A]),
            (PROFILE_B, PROFILE_DESC[PROFILE_B]),
            (PROFILE_C, PROFILE_DESC[PROFILE_C]),
            (PROFILE_D, PROFILE_DESC[PROFILE_D]),
            (PROFILE_E, PROFILE_DESC[PROFILE_E]),
            (PROFILE_F, PROFILE_DESC[PROFILE_F]),
            (PROFILE_G, PROFILE_DESC[PROFILE_G]),
            (PROFILE_H, PROFILE_DESC[PROFILE_H]),
        ]

