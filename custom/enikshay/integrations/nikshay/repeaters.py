from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse

from corehq.apps.locations.models import SQLLocation
from corehq.apps.repeaters.models import CaseRepeater
from corehq.form_processor.models import CommCareCaseSQL
from corehq.toggles import NIKSHAY_INTEGRATION
from casexml.apps.case.xml.parser import CaseUpdateAction
from casexml.apps.case.xform import get_case_updates
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.apps.repeaters.signals import create_repeat_records
from custom.enikshay.case_utils import (
    get_person_case_from_episode,
    get_open_episode_case_from_person,
)
from custom.enikshay.exceptions import NikshayLocationNotFound


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
        if allowed_case_types_and_users:
            episode_case_properties = episode_case.dynamic_case_properties()
            person_case = get_person_case_from_episode(episode_case.domain, episode_case.get_id)

            return (
                not episode_case_properties.get('nikshay_registered', 'false') == 'true' and
                not episode_case_properties.get('nikshay_id', False) and
                episode_pending_registration_changed(episode_case) and
                not test_submission(person_case)
            )
        else:
            return False


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
        # episode.nikshay_registered is true and nikshay_id present and
        # person.hiv_status changed OR
        # CPTDeliverDate changes OR
        # InitiatedDate/Art Initiated date changes
        allowed_case_types_and_users = self._allowed_case_type(person_case) and self._allowed_user(person_case)
        if allowed_case_types_and_users:
            episode_case = get_open_episode_case_from_person(person_case.domain, person_case.get_id)
            episode_case_properties = episode_case.dynamic_case_properties()

            return allowed_case_types_and_users and (
                episode_case_properties.get('nikshay_registered', 'false') == 'true' and
                episode_case_properties.get('nikshay_id') and
                not test_submission(person_case) and
                (
                    related_dates_changed(person_case) or
                    person_hiv_status_changed(person_case)
                )
            )
        else:
            return False


def test_submission(person_case):
    try:
        phi_location = SQLLocation.objects.get(location_id=person_case.owner_id)
    except SQLLocation.DoesNotExist:
        raise NikshayLocationNotFound(
            "Location with id {location_id} not found. This is the owner for person with id: {person_id}"
            .format(location_id=person_case.owner_id, person_id=person_case.case_id)
        )
    return phi_location.metadata.get('is_test', "yes") == "yes"


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


def related_dates_changed(case):
    last_case_action = case.actions[-1]
    if last_case_action.is_case_create:
        return False

    last_update_actions = [update.get_update_action() for update in get_case_updates(last_case_action.form)]
    value_changed = any(
        action for action in last_update_actions
        if isinstance(action, CaseUpdateAction) and (
            'art_initiation_date' in action.dynamic_properties or
            'cpt_initiation_date' in action.dynamic_properties
        )
    )
    return value_changed


def create_case_repeat_records(sender, case, **kwargs):
    create_repeat_records(NikshayRegisterPatientRepeater, case)


def create_hiv_test_repeat_records(sender, case, **kwargs):
    create_repeat_records(NikshayHIVTestRepeater, case)

case_post_save.connect(create_case_repeat_records, CommCareCaseSQL)
case_post_save.connect(create_hiv_test_repeat_records, CommCareCaseSQL)

# TODO: Remove this when eNikshay gets migrated to SQL
case_post_save.connect(create_case_repeat_records, CommCareCase)
case_post_save.connect(create_hiv_test_repeat_records, CommCareCase)
