from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse
from corehq.apps.repeaters.models import CaseRepeater
from corehq.form_processor.models import CommCareCaseSQL
from corehq.toggles import NIKSHAY_INTEGRATION
from casexml.apps.case.xml.parser import CaseUpdateAction
from casexml.apps.case.xform import get_case_updates
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.apps.repeaters.signals import create_repeat_records
from ...case_utils import (
    get_episode_case_from_test,
    get_open_episode_case_from_person,
)


class NikshayRegisterPatientRepeater(CaseRepeater):
    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward eNikshay Patients to Nikshay")

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
            episode_pending_registration_changed(episode_case)
        )


class NikshayFollowupRepeater(CaseRepeater):
    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward eNikshay Patient's Follow Ups to Nikshay")

    @classmethod
    def available_for_domain(cls, domain):
        return NIKSHAY_INTEGRATION.enabled(domain)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.nikshay.views import NikshayPatientFollowupRepeaterView
        return reverse(NikshayPatientFollowupRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, test_case):
        # test.date_tested populates and test.nikshay_registered is false
        # test.test_type_value = microscopy-zn or test.test_type_value = microscopy-fluorescent
        # and episode.nikshay_registered is true
        allowed_case_types_and_users = self._allowed_case_type(test_case) and self._allowed_user(test_case)
        episode_case = get_episode_case_from_test(test_case.get_id)
        test_case_properties = test_case.dynamic_case_properties()
        episode_case_properties = episode_case.dynamic_case_properties()
        return allowed_case_types_and_users and (
            date_tested_added_for_test(test_case) and
            test_case_properties.get('nikshay_registered', 'false') == 'false' and
            test_case_properties.get('test_type_value', '') in ['microscopy-zn', 'microscopy-fluorescent'] and
            episode_case_properties.get('nikshay_registered', 'false') == 'true'
        )


class NikshayHIVTestRepeater(CaseRepeater):
    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward eNikshay Patient's HIV Test to Nikshay")

    @classmethod
    def available_for_domain(cls, domain):
        return NIKSHAY_INTEGRATION.enabled(domain)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.nikshay.views import NikshayHIVTestRepeaterView
        return reverse(NikshayHIVTestRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, person_case):
        # person.hiv_status changed
        # episode.nikshay_registered is true
        allowed_case_types_and_users = self._allowed_case_type(person_case) and self._allowed_user(person_case)
        episode_case = get_open_episode_case_from_person(person_case)
        episode_case_properties = episode_case.dynamic_case_properties()
        return allowed_case_types_and_users and (
            person_hiv_status_changed(person_case) and
            episode_case_properties.get('nikshay_registered', 'false') == 'true'
        )


def episode_pending_registration_changed(case):
    last_case_action = case.actions[-1]
    if last_case_action.is_case_create:
        return False

    last_update_actions = [update.get_update_action() for update in get_case_updates(last_case_action.form)]
    value_changed = any(
        action for action in last_update_actions
        if isinstance(action, CaseUpdateAction)
        and 'episode_pending_registration' in action.dynamic_properties
        and action.dynamic_properties['episode_pending_registration'] == 'no'
    )
    return value_changed


def person_hiv_status_changed(case):
    last_case_action = case.actions[-1]
    if last_case_action.is_case_create:
        return False

    last_update_actions = [update.get_update_action() for update in get_case_updates(last_case_action.form)]
    value_changed = any(
        action for action in last_update_actions
        if isinstance(action, CaseUpdateAction) and 'hiv_status' in action.dynamic_properties
    )
    return value_changed


def date_tested_added_for_test(case):
    last_case_action = case.actions[-1]
    if last_case_action.is_case_create:
        return False

    last_update_actions = [update.get_update_action() for update in get_case_updates(last_case_action.form)]
    value_changed = any(
        action for action in last_update_actions
        if isinstance(action, CaseUpdateAction) and 'date_tested' in action.dynamic_properties
    )
    return value_changed


def create_case_repeat_records(sender, case, **kwargs):
    create_repeat_records(NikshayRegisterPatientRepeater, case)


def create_followup_repeat_records(sender, case, **kwargs):
    create_repeat_records(NikshayFollowupRepeater, case)


def create_hiv_test_repeat_records(sender, case, **kwargs):
    create_repeat_records(NikshayHIVTestRepeater, case)

case_post_save.connect(create_case_repeat_records, CommCareCaseSQL)
case_post_save.connect(create_followup_repeat_records, CommCareCaseSQL)
case_post_save.connect(create_hiv_test_repeat_records, CommCareCaseSQL)

# TODO: Remove this when eNikshay gets migrated to SQL
case_post_save.connect(create_case_repeat_records, CommCareCase)
case_post_save.connect(create_followup_repeat_records, CommCareCaseSQL)
case_post_save.connect(create_hiv_test_repeat_records, CommCareCaseSQL)
