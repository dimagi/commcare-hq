from corehq.toggles import NINETYNINE_DOTS
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from corehq.form_processor.models import CommCareCaseSQL
from casexml.apps.case.models import CommCareCase

from corehq.apps.repeaters.models import CaseRepeater
from corehq.apps.repeaters.signals import create_repeat_records
from casexml.apps.case.signals import case_post_save
from casexml.apps.case.xform import get_case_updates

from custom.enikshay.case_utils import get_open_episode_case_from_person


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
        allowed_case_types_and_users = self._allowed_case_type(case) and self._allowed_user(case)
        case_properties = case.dynamic_case_properties()
        enabled = case_properties.get('dots_99_enabled') == 'true'
        not_registered = (
            case_properties.get('dots_99_registered') == 'false' or
            case_properties.get('dots_99_registered') is None
        )
        return allowed_case_types_and_users and enabled and not_registered

    def allow_retries(self, response):
        if response is not None and response.status_code == 500:
            return True
        return False


class NinetyNineDotsUpdatePatientRepeater(NinetyNineDotsRegisterPatientRepeater):
    friendly_name = _("99DOTS Patient Update")

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.ninetyninedots.views import UpdatePatientRepeaterView
        return reverse(UpdatePatientRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, case):
        # checks whitelisted case types and users
        allowed_case_types_and_users = self._allowed_case_type(case) and self._allowed_user(case)
        if not allowed_case_types_and_users:
            return False

        return (
            phone_number_changed(case) and
            episode_registered_with_99dots(
                get_open_episode_case_from_person(case.domain, case.case_id)
            )
        )


def episode_registered_with_99dots(episode):
    return episode.dynamic_case_properties().get('dots_99_registered', False) == 'true'


def phone_number_changed(case):
    last_case_action = case.actions[-1]
    if last_case_action.is_case_create:
        return False

    update_actions = [update.get_update_action() for update in get_case_updates(last_case_action.form)]
    phone_number_changed = any(
        action for action in update_actions
        if 'mobile_number' in action.dynamic_properties or
        'backup_number' in action.dynamic_properties
    )
    return phone_number_changed


def create_case_repeat_records(sender, case, **kwargs):
    create_repeat_records(NinetyNineDotsRegisterPatientRepeater, case)
    create_repeat_records(NinetyNineDotsUpdatePatientRepeater, case)

case_post_save.connect(create_case_repeat_records, CommCareCaseSQL)

# TODO: Remove this when eNikshay gets migrated to SQL
case_post_save.connect(create_case_repeat_records, CommCareCase)
