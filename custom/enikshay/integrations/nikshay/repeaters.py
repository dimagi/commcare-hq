from django.utils.translation import ugettext_lazy as _
from django.urls import reverse

from corehq.motech.repeaters.models import CaseRepeater, SOAPRepeaterMixin
from corehq.form_processor.models import CommCareCaseSQL
from corehq.toggles import NIKSHAY_INTEGRATION
from casexml.apps.case.xml.parser import CaseUpdateAction
from casexml.apps.case.xform import get_case_updates
from casexml.apps.case.signals import case_post_save
from corehq.motech.repeaters.signals import create_repeat_records
from custom.enikshay.case_utils import (
    get_person_case_from_episode,
    get_open_episode_case_from_person,
    get_occurrence_case_from_test,
    get_open_episode_case_from_occurrence,
)
from custom.enikshay.exceptions import ENikshayCaseNotFound
from custom.enikshay.const import (
    TREATMENT_OUTCOME,
    EPISODE_PENDING_REGISTRATION,
    PRIVATE_PATIENT_EPISODE_PENDING_REGISTRATION,
    DSTB_EPISODE_TYPE,
)
from custom.enikshay.integrations.nikshay.repeater_generator import \
    NikshayRegisterPatientPayloadGenerator, NikshayHIVTestPayloadGenerator, \
    NikshayTreatmentOutcomePayload, NikshayFollowupPayloadGenerator, NikshayRegisterPrivatePatientPayloadGenerator
from custom.enikshay.integrations.utils import (
    is_valid_person_submission,
    is_valid_test_submission,
    is_valid_archived_submission,
)


from custom.enikshay.integrations.utils import case_properties_changed
from custom.enikshay.integrations.nikshay.field_mappings import treatment_outcome


class BaseNikshayRepeater(CaseRepeater):
    @classmethod
    def available_for_domain(cls, domain):
        return NIKSHAY_INTEGRATION.enabled(domain)


class NikshayRegisterPatientRepeater(BaseNikshayRepeater):
    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward eNikshay Patients to Nikshay (episode case type)")

    payload_generator_classes = (NikshayRegisterPatientPayloadGenerator,)

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
            try:
                person_case = get_person_case_from_episode(episode_case.domain, episode_case.get_id)
            except ENikshayCaseNotFound:
                return False
            return (
                not episode_case_properties.get('nikshay_registered', 'false') == 'true' and
                not episode_case_properties.get('nikshay_id', False) and
                episode_case_properties.get('episode_type') == DSTB_EPISODE_TYPE and
                case_properties_changed(episode_case, [EPISODE_PENDING_REGISTRATION]) and
                episode_case_properties.get(EPISODE_PENDING_REGISTRATION, 'yes') == 'no' and
                is_valid_person_submission(person_case)
            )
        else:
            return False


class NikshayHIVTestRepeater(BaseNikshayRepeater):
    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward eNikshay Patient's HIV Test to Nikshay (person case type)")

    payload_generator_classes = (NikshayHIVTestPayloadGenerator,)

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
            try:
                episode_case = get_open_episode_case_from_person(person_case.domain, person_case.get_id)
            except ENikshayCaseNotFound:
                return False
            episode_case_properties = episode_case.dynamic_case_properties()

            return (
                episode_case_properties.get('nikshay_id') and
                (
                    related_dates_changed(person_case) or
                    person_hiv_status_changed(person_case)
                ) and
                is_valid_person_submission(person_case)
            )
        else:
            return False


class NikshayTreatmentOutcomeRepeater(BaseNikshayRepeater):
    class Meta(object):
        app_label = 'repeaters'

    friendly_name = _("Forward Treatment Outcomes to Nikshay (episode case type)")

    payload_generator_classes = (NikshayTreatmentOutcomePayload,)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.nikshay.views import NikshayTreatmentOutcomesView
        return reverse(NikshayTreatmentOutcomesView.urlname, args=[domain])

    def allowed_to_forward(self, episode_case):
        allowed_case_types_and_users = self._allowed_case_type(episode_case) and self._allowed_user(episode_case)
        if not allowed_case_types_and_users:
            return False

        episode_case_properties = episode_case.dynamic_case_properties()
        return (
            episode_case_properties.get('nikshay_id', False) and
            case_properties_changed(episode_case, [TREATMENT_OUTCOME]) and
            episode_case_properties.get(TREATMENT_OUTCOME) in treatment_outcome.keys() and
            is_valid_archived_submission(episode_case)
        )


class NikshayFollowupRepeater(BaseNikshayRepeater):
    followup_for_tests = ['end_of_ip', 'end_of_cp']

    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward eNikshay Patient's Follow Ups to Nikshay (test case type)")

    payload_generator_classes = (NikshayFollowupPayloadGenerator,)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.nikshay.views import NikshayPatientFollowupRepeaterView
        return reverse(NikshayPatientFollowupRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, test_case):
        # test.date_reported populates and test.nikshay_registered is false
        # test.test_type_value = microscopy-zn or test.test_type_value = microscopy-fluorescent
        # and episode.nikshay_registered is true
        allowed_case_types_and_users = self._allowed_case_type(test_case) and self._allowed_user(test_case)
        if allowed_case_types_and_users:
            try:
                occurence_case = get_occurrence_case_from_test(test_case.domain, test_case.get_id)
                episode_case = get_open_episode_case_from_occurrence(test_case.domain, occurence_case.get_id)
            except ENikshayCaseNotFound:
                return False
            test_case_properties = test_case.dynamic_case_properties()
            episode_case_properties = episode_case.dynamic_case_properties()
            return (
                test_case_properties.get('nikshay_registered', 'false') == 'false' and
                test_case_properties.get('test_type_value', '') in ['microscopy-zn', 'microscopy-fluorescent'] and
                episode_case_properties.get('nikshay_id') and
                (
                    test_case_properties.get('purpose_of_testing') == 'diagnostic' or
                    test_case_properties.get('follow_up_test_reason') in self.followup_for_tests or
                    test_case_properties.get('rft_general') in ['diagnosis_dstb', 'diagnosis_drtb'] or
                    test_case_properties.get('rft_dstb_followup') in self.followup_for_tests
                ) and
                case_properties_changed(test_case, 'date_reported') and
                not is_valid_test_submission(test_case)
            )
        else:
            return False


class NikshayRegisterPrivatePatientRepeater(SOAPRepeaterMixin, BaseNikshayRepeater):

    payload_generator_classes = (NikshayRegisterPrivatePatientPayloadGenerator,)

    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward eNikshay Private Patients to Nikshay (episode case type)")

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.nikshay.views import RegisterNikshayPrivatePatientRepeaterView
        return reverse(RegisterNikshayPrivatePatientRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, episode_case):
        allowed_case_types_and_users = self._allowed_case_type(episode_case) and self._allowed_user(episode_case)
        if not allowed_case_types_and_users:
            return False

        try:
            person_case = get_person_case_from_episode(episode_case.domain, episode_case.get_id)
        except ENikshayCaseNotFound:
            return False

        episode_case_properties = episode_case.dynamic_case_properties()
        return (
            episode_case_properties.get('nikshay_registered', 'false') == 'false' and
            not episode_case_properties.get('nikshay_id') and
            case_properties_changed(episode_case, [PRIVATE_PATIENT_EPISODE_PENDING_REGISTRATION]) and
            episode_case_properties.get(PRIVATE_PATIENT_EPISODE_PENDING_REGISTRATION, 'yes') == 'no' and
            is_valid_person_submission(person_case)
        )


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
            'cpt_1_date' in action.dynamic_properties
        )
    )
    return value_changed


def create_nikshay_case_repeat_records(sender, case, **kwargs):
    create_repeat_records(NikshayRegisterPatientRepeater, case)
    create_repeat_records(NikshayTreatmentOutcomeRepeater, case)
    create_repeat_records(NikshayFollowupRepeater, case)
    create_repeat_records(NikshayRegisterPrivatePatientRepeater, case)
    create_repeat_records(NikshayHIVTestRepeater, case)

case_post_save.connect(create_nikshay_case_repeat_records, CommCareCaseSQL)
