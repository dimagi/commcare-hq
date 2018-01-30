from __future__ import absolute_import
import re

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse

from corehq.apps.locations.models import SQLLocation
from dimagi.utils.post import parse_SOAP_response
from corehq.motech.repeaters.models import CaseRepeater, SOAPRepeaterMixin, LocationRepeater
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
    person_has_any_legacy_nikshay_notifiable_episode,
    get_person_case_from_occurrence)
from custom.enikshay.exceptions import ENikshayCaseNotFound
from custom.enikshay.const import (
    TREATMENT_OUTCOME,
    EPISODE_PENDING_REGISTRATION,
    PRIVATE_PATIENT_EPISODE_PENDING_REGISTRATION,
    HEALTH_ESTABLISHMENT_TYPES_TO_FORWARD,
    DSTB_EPISODE_TYPE,
    HEALTH_ESTABLISHMENT_SUCCESS_RESPONSE_REGEX,
    TREATMENT_INITIATED_IN_PHI,
    ENROLLED_IN_PRIVATE,
)
from custom.enikshay.integrations.nikshay.repeater_generator import (
    NikshayRegisterPatientPayloadGenerator,
    NikshayHIVTestPayloadGenerator,
    NikshayTreatmentOutcomePayload,
    NikshayFollowupPayloadGenerator,
    NikshayRegisterPrivatePatientPayloadGenerator,
    NikshayHealthEstablishmentPayloadGenerator,
    NikshayRegisterPatientPayloadGeneratorV2,
)
from custom.enikshay.integrations.utils import (
    is_valid_person_submission,
    is_valid_test_submission,
    is_valid_archived_submission,
)

from custom.enikshay.integrations.utils import case_properties_changed
from custom.enikshay.integrations.nikshay.field_mappings import treatment_outcome


class BaseNikshayRepeater(CaseRepeater):
    @property
    def verify(self):
        return False

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
                valid_nikshay_patient_registration(episode_case_properties) and
                case_properties_changed(episode_case, [EPISODE_PENDING_REGISTRATION]) and
                is_valid_person_submission(person_case)
            )
        else:
            return False


class NikshayRegisterPatientRepeaterV2(BaseNikshayRepeater):
    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward eNikshay Patients to Nikshay (episode case type) V2")

    payload_generator_classes = (NikshayRegisterPatientPayloadGeneratorV2,)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.nikshay.views import RegisterNikshayPatientRepeaterViewV2
        return reverse(RegisterNikshayPatientRepeaterViewV2.urlname, args=[domain])

    def allowed_to_forward(self, episode_case):
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
        person_case_properties = person_case.dynamic_case_properties()
        if allowed_case_types_and_users:
            return (
                # Do not attempt notification for patients registered in private app
                not (person_case_properties.get(ENROLLED_IN_PRIVATE) == 'true') and
                (
                    related_dates_changed(person_case) or
                    person_hiv_status_changed(person_case)
                ) and
                is_valid_person_submission(person_case) and
                person_has_any_legacy_nikshay_notifiable_episode(person_case)
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
            not (episode_case_properties.get(ENROLLED_IN_PRIVATE) == 'true') and
            (  # has a nikshay id already or is a valid submission probably waiting notification
                episode_case_properties.get('nikshay_id') or
                valid_nikshay_patient_registration(episode_case_properties)
            ) and
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
            occurrence_case = get_occurrence_case_from_test(test_case.domain, test_case.case_id)
            person_case = get_person_case_from_occurrence(test_case.domain, occurrence_case.case_id)
            test_case_properties = test_case.dynamic_case_properties()
            return (
                not (test_case_properties.get(ENROLLED_IN_PRIVATE) == 'true') and
                test_case_properties.get('nikshay_registered', 'false') == 'false' and
                test_case_properties.get('test_type_value', '') in ['microscopy-zn', 'microscopy-fluorescent'] and
                (
                    test_case_properties.get('purpose_of_testing') == 'diagnostic' or
                    test_case_properties.get('follow_up_test_reason') in self.followup_for_tests or
                    test_case_properties.get('rft_general') in ['diagnosis_dstb', 'diagnosis_drtb'] or
                    test_case_properties.get('rft_dstb_followup') in self.followup_for_tests
                ) and
                case_properties_changed(test_case, 'date_reported') and
                not is_valid_test_submission(test_case) and
                person_has_any_legacy_nikshay_notifiable_episode(person_case)
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
            episode_case_properties.get('private_nikshay_registered', 'false') == 'false' and
            not episode_case_properties.get('nikshay_id') and
            valid_nikshay_patient_registration(episode_case_properties, private_registration=True) and
            case_properties_changed(episode_case, [PRIVATE_PATIENT_EPISODE_PENDING_REGISTRATION]) and
            is_valid_person_submission(person_case)
        )

    def handle_response(self, result, repeat_record):
        if isinstance(result, Exception):
            attempt = repeat_record.handle_exception(result)
            self.generator.handle_exception(result, repeat_record)
            return attempt
        # A successful response returns a Nikshay ID like 00001
        # Failures also return with status code 200 and some message like
        # Dublicate Entry or Invalid data format
        # (Dublicate is not a typo)
        message = parse_SOAP_response(
            repeat_record.repeater.url,
            repeat_record.repeater.operation,
            result,
            verify=self.verify
        )
        if isinstance(message, basestring) and message.isdigit():
            attempt = repeat_record.handle_success(result)
            self.generator.handle_success(result, self.payload_doc(repeat_record), repeat_record)
        else:
            attempt = repeat_record.handle_failure(result)
            self.generator.handle_failure(result, self.payload_doc(repeat_record), repeat_record)
        return attempt


class NikshayHealthEstablishmentRepeater(SOAPRepeaterMixin, LocationRepeater):
    payload_generator_classes = (NikshayHealthEstablishmentPayloadGenerator,)

    class Meta(object):
        app_label = 'repeaters'

    include_app_id_param = False
    friendly_name = _("Forward Nikshay Health Establishments")

    @classmethod
    def available_for_domain(cls, domain):
        return NIKSHAY_INTEGRATION.enabled(domain)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.nikshay.views import RegisterNikshayHealthEstablishmentRepeaterView
        return reverse(RegisterNikshayHealthEstablishmentRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, location):
        return (
            not location.metadata.get('is_test', "yes") == "yes" and
            location.location_type.name in HEALTH_ESTABLISHMENT_TYPES_TO_FORWARD and
            not location.metadata.get('nikshay_code')
        )

    def handle_response(self, result, repeat_record):
        if isinstance(result, Exception):
            attempt = repeat_record.handle_exception(result)
            self.generator.handle_exception(result, repeat_record)
            return attempt
        # A successful response looks like HE_ID: 125344
        # Failures also return with status code 200 and some message like
        # Character are not allowed........
        # (........ is a part of the actual message)
        message = parse_SOAP_response(
            repeat_record.repeater.url,
            repeat_record.repeater.operation,
            result,
            verify=self.verify
        )
        # message does not give the final node message here so need to find the real message
        # look at SUCCESSFUL_HEALTH_ESTABLISHMENT_RESPONSE for example
        message_node = message.find("NewDataSet/HE_DETAILS/Message")
        if message_node:
            message_text = message_node.text
        if message_node and re.search(HEALTH_ESTABLISHMENT_SUCCESS_RESPONSE_REGEX, message_text):
            attempt = repeat_record.handle_success(result)
            self.generator.handle_success(result, self.payload_doc(repeat_record), repeat_record)
        else:
            attempt = repeat_record.handle_failure(result)
            self.generator.handle_failure(result, self.payload_doc(repeat_record), repeat_record)
        return attempt


def valid_nikshay_patient_registration(episode_case_properties, private_registration=False):
    if private_registration:
        registration_prop = PRIVATE_PATIENT_EPISODE_PENDING_REGISTRATION
    else:
        registration_prop = EPISODE_PENDING_REGISTRATION

    # check for registration done and confirmed episode type
    should_notify = (
        episode_case_properties.get('episode_type') == DSTB_EPISODE_TYPE and
        episode_case_properties.get(registration_prop, 'yes') == 'no'
    )

    if not private_registration:
        # check for treatment initiated within the phi itself to have all required information on payload
        return should_notify and episode_case_properties.get('treatment_initiated') == TREATMENT_INITIATED_IN_PHI
    return should_notify


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


@receiver(post_save, sender=SQLLocation, dispatch_uid="create_nikshay_he_repeat_records")
def create_location_repeat_records(sender, raw=False, **kwargs):
    if raw:
        return
    create_repeat_records(NikshayHealthEstablishmentRepeater, kwargs['instance'])


def create_nikshay_case_repeat_records(sender, case, **kwargs):
    create_repeat_records(NikshayRegisterPatientRepeater, case)
    create_repeat_records(NikshayTreatmentOutcomeRepeater, case)
    create_repeat_records(NikshayFollowupRepeater, case)
    create_repeat_records(NikshayRegisterPrivatePatientRepeater, case)
    create_repeat_records(NikshayHIVTestRepeater, case)

case_post_save.connect(create_nikshay_case_repeat_records, CommCareCaseSQL)
