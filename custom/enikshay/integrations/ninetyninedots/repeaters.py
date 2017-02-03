from corehq.toggles import NINETYNINE_DOTS
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from corehq.form_processor.models import CommCareCaseSQL
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xml.parser import CaseUpdateAction

from corehq.apps.repeaters.models import CaseRepeater
from corehq.apps.repeaters.signals import create_repeat_records
from casexml.apps.case.signals import case_post_save
from casexml.apps.case.xform import get_case_updates

from custom.enikshay.case_utils import (
    get_open_episode_case_from_person,
    get_episode_case_from_adherence
)
from custom.enikshay.const import PRIMARY_PHONE_NUMBER, BACKUP_PHONE_NUMBER, TREATMENT_OUTCOME
from custom.enikshay.exceptions import ENikshayCaseNotFound


class Base99DOTSRepeater(CaseRepeater):
    class Meta(object):
        app_label = 'repeaters'

    @classmethod
    def available_for_domain(cls, domain):
        return NINETYNINE_DOTS.enabled(domain)

    def allow_retries(self, response):
        if response is not None and response.status_code == 500:
            return True
        return False


class NinetyNineDotsRegisterPatientRepeater(Base99DOTSRepeater):
    """Register a patient in 99DOTS
    Case Type: Episode
    Trigger: When episode.dots_99_enabled is true, but episode.dots_99_registered is false
    Side Effects:
        Success: episode.dots_99_registered = true, dots_99_error = ''
        Error: dots_99_error = 'error message'
    Endpoint: https://www.99dots.org/Dimagi99DOTSAPI/registerPatient

    """

    friendly_name = _("99DOTS Patient Registration (episode case type)")

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.ninetyninedots.views import RegisterPatientRepeaterView
        return reverse(RegisterPatientRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, case):
        # checks whitelisted case types and users
        allowed_case_types_and_users = self._allowed_case_type(case) and self._allowed_user(case)
        case_properties = case.dynamic_case_properties()
        enabled = case_properties.get('dots_99_enabled') == 'true'
        not_registered = (
            case_properties.get('dots_99_registered') == 'false' or
            case_properties.get('dots_99_registered') is None
        )
        return allowed_case_types_and_users and enabled and not_registered


class NinetyNineDotsUpdatePatientRepeater(Base99DOTSRepeater):
    """Update patient records a patient in 99DOTS
    Case Type: Person
    Trigger: When phone number changes
    Side Effects:
        Error: dots_99_error = 'error message'
    Endpoint: https://www.99dots.org/Dimagi99DOTSAPI/updatePatient

    """

    friendly_name = _("99DOTS Patient Update (person case type)")

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.ninetyninedots.views import UpdatePatientRepeaterView
        return reverse(UpdatePatientRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, case):
        if not self._allowed_case_type(case) and self._allowed_user(case):
            return False

        try:
            registered_episode = episode_registered_with_99dots(
                get_open_episode_case_from_person(case.domain, case.case_id)
            )
        except ENikshayCaseNotFound:
            return False

        return phone_number_changed(case) and registered_episode


class NinetyNineDotsAdherenceRepeater(Base99DOTSRepeater):
    """Send Adherence datapoints to 99DOTS
    Case Type: Adherence
    Trigger: When a new adherence datapoint is collected in eNikshay when a patient is enrolled in 99DOTS
    Side Effects:
        Success: adherence.dots_99_updated = true
        Error: adherence.dots_99_updated = false, adherence.dots_99_error = 'error message'
    Endpoint: https://www.99dots.org/Dimagi99DOTSAPI/updateAdherenceInformation

    """
    friendly_name = _("99DOTS Update Adherence (adherence case type)")

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.ninetyninedots.views import UpdateAdherenceRepeaterView
        return reverse(UpdateAdherenceRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, adherence_case):
        allowed_case_types_and_users = (
            self._allowed_case_type(adherence_case) and self._allowed_user(adherence_case)
        )
        if not allowed_case_types_and_users:
            return False

        episode_case = get_episode_case_from_adherence(adherence_case.domain, adherence_case.case_id)
        episode_case_properties = episode_case.dynamic_case_properties()
        adherence_case_properties = adherence_case.dynamic_case_properties()

        enabled = episode_case_properties.get('dots_99_enabled') == 'true'
        registered = episode_case_properties.get('dots_99_registered') == 'true'
        from_enikshay = adherence_case_properties.get('adherence_source') == 'enikshay'
        previously_updated = adherence_case_properties.get('dots_99_updated') == 'true'
        return enabled and registered and from_enikshay and not previously_updated


class NinetyNineDotsTreatmentOutcomeRepeater(Base99DOTSRepeater):
    """Update treatment outcomes in 99DOTS
    Case Type: Episode
    Trigger: When a treatment outcome is collected for an episode that is registered in 99DOTS
    Side Effects:
        Success: episode.dots_99_treatment_outcome_updated = 'true'
        Error: episode.dots_99_error = 'error message'
    Endpoint: https://www.99dots.org/Dimagi99DOTSAPI/closeCase

    """
    friendly_name = _("99DOTS Update Treatment Outcome (episode case type)")

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.ninetyninedots.views import UpdateTreatmentOutcomeRepeaterView
        return reverse(UpdateTreatmentOutcomeRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, episode_case):
        allowed_case_types_and_users = (
            self._allowed_case_type(episode_case) and self._allowed_user(episode_case)
        )
        if not allowed_case_types_and_users:
            return False

        episode_case_properties = episode_case.dynamic_case_properties()
        enabled = episode_case_properties.get('dots_99_enabled') == 'true'
        registered = episode_case_properties.get('dots_99_registered') == 'true'
        return enabled and registered and treatment_outcome_changed(episode_case)


def episode_registered_with_99dots(episode):
    return episode.dynamic_case_properties().get('dots_99_registered', False) == 'true'


def treatment_outcome_changed(case):
    last_case_action = case.actions[-1]
    if last_case_action.is_case_create:
        return False

    update_actions = [update.get_update_action() for update in get_case_updates(last_case_action.form)]
    treatment_outcome_changed = any(
        action for action in update_actions
        if isinstance(action, CaseUpdateAction)
        and (TREATMENT_OUTCOME in action.dynamic_properties)
    )
    return treatment_outcome_changed


def phone_number_changed(case):
    last_case_action = case.actions[-1]
    if last_case_action.is_case_create:
        return False

    update_actions = [update.get_update_action() for update in get_case_updates(last_case_action.form)]
    phone_number_changed = any(
        action for action in update_actions
        if isinstance(action, CaseUpdateAction)
        and (PRIMARY_PHONE_NUMBER in action.dynamic_properties or
             BACKUP_PHONE_NUMBER in action.dynamic_properties)
    )
    return phone_number_changed


def create_case_repeat_records(sender, case, **kwargs):
    create_repeat_records(NinetyNineDotsRegisterPatientRepeater, case)
    create_repeat_records(NinetyNineDotsUpdatePatientRepeater, case)
    create_repeat_records(NinetyNineDotsAdherenceRepeater, case)
    create_repeat_records(NinetyNineDotsTreatmentOutcomeRepeater, case)

case_post_save.connect(create_case_repeat_records, CommCareCaseSQL)

# TODO: Remove this when eNikshay gets migrated to SQL
case_post_save.connect(create_case_repeat_records, CommCareCase)
