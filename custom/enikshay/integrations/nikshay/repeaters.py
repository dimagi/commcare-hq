from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse
from corehq.apps.repeaters.models import CaseRepeater
from corehq.form_processor.models import CommCareCaseSQL
from corehq.toggles import NIKSHAY_INTEGRATION
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.apps.repeaters.signals import create_repeat_records
from custom.enikshay.case_utils import case_properties_changed
from custom.enikshay.const import TREATMENT_OUTCOME, EPISODE_PENDING_REGISTRATION


class NikshayRegisterPatientRepeater(CaseRepeater):
    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward eNikshay Patients to Nikshay (episode case type)")

    @classmethod
    def available_for_domain(cls, domain):
        return NIKSHAY_INTEGRATION.enabled(domain)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.nikshay.views import RegisterNikshayPatientRepeaterView
        return reverse(RegisterNikshayPatientRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, episode_case):
        # When case property episode.episode_pending_registration transitions from 'yes' to 'no',
        # and (episode.nikshay_registered != 'true'  or episode.nikshay_id != '')
        allowed_case_types_and_users = self._allowed_case_type(episode_case) and self._allowed_user(episode_case)
        episode_case_properties = episode_case.dynamic_case_properties()
        return allowed_case_types_and_users and (
            not episode_case_properties.get('nikshay_registered', 'false') == 'true' and
            not episode_case_properties.get('nikshay_id', False) and

            # Episode pending registration flips from yes to no
            case_properties_changed(episode_case, [EPISODE_PENDING_REGISTRATION]) and
            episode_case_properties.get(EPISODE_PENDING_REGISTRATION, 'yes') == 'no'
        )


class NikshayTreatmentOutcomeRepeater(CaseRepeater):
    class Meta(object):
        app_label = 'repeaters'

    friendly_name = _("Forward Treatment Outcomes to Nikshay (episode case type)")

    @classmethod
    def available_for_domain(cls, domain):
        return NIKSHAY_INTEGRATION.enabled(domain)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.nikshay.views import NikshayTreatmentOutcomesView
        return reverse(NikshayTreatmentOutcomesView.urlname, args=[domain])

    def allowed_to_forward(self, episode_case):
        allowed_case_types_and_users = self._allowed_case_type(episode_case) and self._allowed_user(episode_case)
        episode_case_properties = episode_case.dynamic_case_properties()
        return allowed_case_types_and_users and (
            not episode_case_properties.get('nikshay_registered', 'false') == 'true' and
            not episode_case_properties.get('nikshay_id', False) and
            not episode_case_properties.get('treatment_outcome_nikshay_registered', False) == 'true' and
            case_properties_changed(episode_case, [TREATMENT_OUTCOME])
        )


def create_case_repeat_records(sender, case, **kwargs):
    create_repeat_records(NikshayRegisterPatientRepeater, case)
    create_repeat_records(NikshayTreatmentOutcomeRepeater, case)

case_post_save.connect(create_case_repeat_records, CommCareCaseSQL)

# TODO: Remove this when eNikshay gets migrated to SQL
case_post_save.connect(create_case_repeat_records, CommCareCase)
