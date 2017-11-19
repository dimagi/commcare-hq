from __future__ import absolute_import
import json
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from casexml.apps.case.signals import case_post_save
from corehq.apps.locations.models import SQLLocation
from corehq.motech.repeaters.models import CaseRepeater, LocationRepeater, UserRepeater, RepeatRecord
from corehq.motech.repeaters.signals import create_repeat_records
from corehq.apps.users.signals import commcare_user_post_save
from corehq.form_processor.models import CommCareCaseSQL
from corehq.toggles import BETS_INTEGRATION
from corehq.util import reverse
from custom.enikshay.case_utils import CASE_TYPE_PERSON
from custom.enikshay.const import (
    ENROLLED_IN_PRIVATE, PRESCRIPTION_TOTAL_DAYS_THRESHOLD,
    BETS_DATE_PRESCRIPTION_THRESHOLD_MET)
from custom.enikshay.exceptions import ENikshayException
from custom.enikshay.integrations.bets.const import (
    TREATMENT_180_EVENT, DRUG_REFILL_EVENT, SUCCESSFUL_TREATMENT_EVENT,
    DIAGNOSIS_AND_NOTIFICATION_EVENT, AYUSH_REFERRAL_EVENT, CHEMIST_VOUCHER_EVENT,
    LAB_VOUCHER_EVENT, TOTAL_DAY_THRESHOLDS)
from custom.enikshay.integrations.bets.repeater_generators import (
    BETS180TreatmentPayloadGenerator, LabBETSVoucherPayloadGenerator,
    ChemistBETSVoucherPayloadGenerator, BETSAYUSHReferralPayloadGenerator,
    BETSDiagnosisAndNotificationPayloadGenerator, BETSSuccessfulTreatmentPayloadGenerator,
    BETSDrugRefillPayloadGenerator, BETSLocationPayloadGenerator, BETSUserPayloadGenerator,
    BETSBeneficiaryPayloadGenerator)
from custom.enikshay.integrations.utils import (
    case_properties_changed, is_valid_episode_submission, is_valid_voucher_submission,
    is_valid_archived_submission, is_valid_person_submission, case_was_created,
    is_migrated_uatbc_episode, string_to_date_or_None)
from .utils import get_bets_location_json, queued_payload, get_bets_user_json
import six


class BETSRepeaterMixin(object):
    class Meta(object):
        app_label = 'repeaters'

    @classmethod
    def available_for_domain(cls, domain):
        return BETS_INTEGRATION.enabled(domain)

    def _is_successful_response(self, response_json):
        """We can't be certain of the response that BETS is going to send us.

        BETS accepts multiple records, but we only ever send them one.

        1. If they include a "code" param in their response, use this as a marker of success
        2. If they include a meta block in their response, use the information in there as a marker of success.
        3. Otherwise, loop through each result and see if all of them have succeeded.
        4. Otherwise, this was a terrible failure. Try again.
        """

        response_code = response_json.get('code')
        if response_code:
            if 200 <= response_code < 300:
                return True
            else:
                return False

        response_meta = response_json.get('meta')
        if response_meta:
            success_count = response_meta.get('successCount')
            total_count = response_meta.get('totalCount')
            if success_count > 0 and total_count == success_count:
                return True

        response_data = response_json.get('response')
        if response_data:
            return all([response_datum.get('status') == "Success" for response_datum in response_data])

        return False

    def handle_response(self, result, repeat_record):
        """Handle BETS custom responses. They always respond with a 200 status code. 'cause they "OK".

        We only ever send one item at a time, so we should only ever get one
        item at a time. But they send us a list of responses anyway, so we try
        and handle that as best we can.

        Failure response: {"status":"Failed","code":"400"}
        Success response:
            {
                "meta": {
                    "failCount": "0",
                    "successCount": "1",
                    "totalCount": "1",
                },
                "response": [
                    {
                        "status": "Success",
                        "failureDescription": ""
                    }
                ]
            }

        """
        if isinstance(result, Exception):
            attempt = repeat_record.handle_exception(result)
            self.generator.handle_exception(result, repeat_record)
            return attempt

        try:
            response_json = result.json()
        except ValueError:
            # read the spec, bro.
            attempt = repeat_record.handle_exception(result)
            self.generator.handle_exception(result.text, repeat_record)
            return attempt

        if self._is_successful_response(response_json):
            attempt = repeat_record.handle_success(result)
            self.generator.handle_success(result, self.payload_doc(repeat_record), repeat_record)
        else:
            attempt = repeat_record.handle_failure(result)
            self.generator.handle_failure(result, self.payload_doc(repeat_record), repeat_record)

        return attempt


class BaseBETSRepeater(BETSRepeaterMixin, CaseRepeater):
    def case_types_and_users_allowed(self, case):
        return self._allowed_case_type(case) and self._allowed_user(case)


class BaseBETSVoucherRepeater(BaseBETSRepeater):
    """Forward a voucher to BETS
    Case Type: Voucher
    Trigger: When voucher.state transitions to "approved" or "partially_approved"
             and voucher.sent_to_bets != 'true'
    Side Effects:
        Success: voucher.event_{EVENT_ID} = "true" and voucher.bets_{EVENT_ID}_error = ''
        Error: voucher.bets_{EVENT_ID}_error = 'error message'
    """
    event_id = None
    voucher_type = None

    def allowed_to_forward(self, voucher_case):
        if not self.case_types_and_users_allowed(voucher_case):
            return False

        case_properties = voucher_case.dynamic_case_properties()
        correct_voucher_type = case_properties['voucher_type'] == self.voucher_type
        approved = case_properties.get("state") == "approved"
        not_sent = case_properties.get("event_{}".format(self.event_id)) != "sent"
        return (
            approved
            and correct_voucher_type
            and not_sent
            and case_properties_changed(voucher_case, ['state'])
            and is_valid_voucher_submission(voucher_case)
        )


class ChemistBETSVoucherRepeater(BaseBETSVoucherRepeater):
    friendly_name = _("BETS - Chemist Voucher Forwarding (voucher case type)")
    event_id = CHEMIST_VOUCHER_EVENT
    voucher_type = "prescription"

    payload_generator_classes = (ChemistBETSVoucherPayloadGenerator,)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.bets.views import ChemistBETSVoucherRepeaterView
        return reverse(ChemistBETSVoucherRepeaterView.urlname, args=[domain])


class LabBETSVoucherRepeater(BaseBETSVoucherRepeater):
    friendly_name = _("BETS - Lab Voucher Forwarding (voucher case type)")
    event_id = LAB_VOUCHER_EVENT
    voucher_type = "test"

    payload_generator_classes = (LabBETSVoucherPayloadGenerator,)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.bets.views import LabBETSVoucherRepeaterView
        return reverse(LabBETSVoucherRepeaterView.urlname, args=[domain])


def _cast_to_int(string):
    try:
        return int(string)
    except ValueError:
        return 0


class BETS180TreatmentRepeater(BaseBETSRepeater):
    friendly_name = _(
        "BETS - MBBS+ Providers: 180 days of private OR govt. "
        "FDCs with treatment outcome reported (episode case type)"
    )

    payload_generator_classes = (BETS180TreatmentPayloadGenerator,)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.bets.views import BETS180TreatmentRepeaterView
        return reverse(BETS180TreatmentRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, episode_case):
        if not self.case_types_and_users_allowed(episode_case):
            return False

        case_properties = episode_case.dynamic_case_properties()
        prescription_total_days = _cast_to_int(case_properties.get("prescription_total_days", 0))
        treatment_options = case_properties.get("treatment_options")
        if treatment_options == "fdc":
            meets_days_threshold = prescription_total_days >= 168
        else:
            meets_days_threshold = prescription_total_days >= 180

        enrolled_in_private_sector = case_properties.get(ENROLLED_IN_PRIVATE) == 'true'
        not_sent = case_properties.get("event_{}".format(TREATMENT_180_EVENT)) != "sent"
        return (
            meets_days_threshold
            and case_properties_changed(episode_case, ['prescription_total_days'])
            and not_sent
            and enrolled_in_private_sector
            and is_valid_episode_submission(episode_case)
            and not is_migrated_uatbc_episode(episode_case)
        )


class BETSDrugRefillRepeater(BaseBETSRepeater):
    friendly_name = _("BETS - Patients: Cash transfer on subsequent drug refill (episode case type)")

    payload_generator_classes = (BETSDrugRefillPayloadGenerator,)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.bets.views import BETSDrugRefillRepeaterView
        return reverse(BETSDrugRefillRepeaterView.urlname, args=[domain])

    @staticmethod
    def _list_items_unique(l):
        return len(set(l)) == len(l)

    @staticmethod
    def _get_threshold_case_prop(n):
        return PRESCRIPTION_TOTAL_DAYS_THRESHOLD.format(n)

    @staticmethod
    def prescription_total_days_threshold_in_trigger_state(episode_case_properties, n, check_already_sent=True):
        threshold_case_prop = BETSDrugRefillRepeater._get_threshold_case_prop(n)
        if check_already_sent:
            return bool(
                string_to_date_or_None(episode_case_properties.get(threshold_case_prop))
                and episode_case_properties.get("event_{}_{}".format(DRUG_REFILL_EVENT, n)) != "sent"
            )
        else:
            return string_to_date_or_None(episode_case_properties.get(threshold_case_prop)) is not None

    def allowed_to_forward(self, episode_case):
        if not self.case_types_and_users_allowed(episode_case):
            return False

        episode_case_properties = episode_case.dynamic_case_properties()
        trigger_by_threshold = {}  # threshold -> boolean
        threshold_prop_values_by_threshold = {}  # threshold -> date

        for n in TOTAL_DAY_THRESHOLDS:
            threshold_case_prop = self._get_threshold_case_prop(n)
            threshold_prop_values_by_threshold[n] = string_to_date_or_None(
                episode_case_properties.get(threshold_case_prop)
            )
            trigger_for_n = bool(
                self.prescription_total_days_threshold_in_trigger_state(
                    episode_case_properties, n, check_already_sent=True
                )
                and case_properties_changed(episode_case, [threshold_case_prop])
            )
            trigger_by_threshold[n] = trigger_for_n

        trigger_dates_unique = self._list_items_unique(filter(None, threshold_prop_values_by_threshold.values()))
        if not trigger_dates_unique:
            self._flag_program_team()

        return (
            trigger_dates_unique
            and any(trigger_by_threshold.values())
            and is_valid_episode_submission(episode_case)
        )

    def _flag_program_team(self):
        # TODO: Write me
        pass


def xor(a, b):
    return bool(a) ^ bool(b)


class BETSSuccessfulTreatmentRepeater(BaseBETSRepeater):
    friendly_name = _("BETS - Patients: Cash transfer on successful treatment completion (episode case type)")

    payload_generator_classes = (BETSSuccessfulTreatmentPayloadGenerator,)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.bets.views import BETSSuccessfulTreatmentRepeaterView
        return reverse(BETSSuccessfulTreatmentRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, episode_case):
        if not self.case_types_and_users_allowed(episode_case):
            return False

        enrolled_in_private_sector = episode_case.get_case_property(ENROLLED_IN_PRIVATE) == 'true'
        not_sent = episode_case.get_case_property("event_{}".format(SUCCESSFUL_TREATMENT_EVENT)) != "sent"

        return (
            not_sent
            and enrolled_in_private_sector
            and is_valid_archived_submission(episode_case)
            and xor(self._treatment_completed(episode_case),
                    self._met_prescription_days_threshold(episode_case))
        )

    def _treatment_completed(self, episode_case):
        return (
            episode_case.get_case_property("treatment_outcome") in ("cured", "treatment_completed")
            and case_properties_changed(episode_case, ["treatment_outcome"])
        )

    def _met_prescription_days_threshold(self, episode_case):
        return case_properties_changed(episode_case, [BETS_DATE_PRESCRIPTION_THRESHOLD_MET])


class BETSDiagnosisAndNotificationRepeater(BaseBETSRepeater):
    friendly_name = _("BETS - Providers: For diagnosis and notification of TB case (episode case type)")

    payload_generator_classes = (BETSDiagnosisAndNotificationPayloadGenerator,)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.bets.views import BETSDiagnosisAndNotificationRepeaterView
        return reverse(BETSDiagnosisAndNotificationRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, episode_case):
        if not self.case_types_and_users_allowed(episode_case):
            return False

        case_properties = episode_case.dynamic_case_properties()
        not_sent = case_properties.get("event_{}".format(DIAGNOSIS_AND_NOTIFICATION_EVENT)) != "sent"
        enrolled_in_private_sector = case_properties.get(ENROLLED_IN_PRIVATE) == 'true'
        return (
            case_properties.get("bets_first_prescription_voucher_redeemed") == 'true'
            and not_sent
            and enrolled_in_private_sector
            and case_properties_changed(episode_case, ['bets_first_prescription_voucher_redeemed'])
            and is_valid_episode_submission(episode_case)
            and not is_migrated_uatbc_episode(episode_case)
        )


class BETSAYUSHReferralRepeater(BaseBETSRepeater):
    friendly_name = _("BETS - AYUSH/Other provider: Registering and referral of a presumptive TB case"
                      " in eNikshay (episode case type)")

    payload_generator_classes = (BETSAYUSHReferralPayloadGenerator,)

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.bets.views import BETSAYUSHReferralRepeaterView
        return reverse(BETSAYUSHReferralRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, episode_case):
        if not self.case_types_and_users_allowed(episode_case):
            return False

        case_properties = episode_case.dynamic_case_properties()
        not_sent = case_properties.get("event_{}".format(AYUSH_REFERRAL_EVENT)) != "sent"
        enrolled_in_private_sector = case_properties.get(ENROLLED_IN_PRIVATE) == 'true'
        return (
            case_properties.get("bets_first_prescription_voucher_redeemed") == 'true'
            and case_properties.get("created_by_user_type") == "pac"
            and not_sent
            and enrolled_in_private_sector
            and case_properties_changed(episode_case, ['bets_first_prescription_voucher_redeemed'])
            and is_valid_episode_submission(episode_case)
            and not is_migrated_uatbc_episode(episode_case)
        )


class BETSUserRepeater(BETSRepeaterMixin, UserRepeater):
    friendly_name = _("BETS - Forward Agency Users")
    payload_generator_classes = (BETSUserPayloadGenerator,)

    location_types_to_forward = ('plc', 'pcp', 'pcc', 'pac')

    def _is_relevant_location(self, location):
        return (location.metadata.get('is_test') != "yes"
                and location.location_type.code in self.location_types_to_forward)

    def get_attempt_info(self, repeat_record):
        """Store the payload as extra information
        """
        try:
            return six.text_type(self.get_payload(repeat_record))
        except ENikshayException:
            return None

    def allowed_to_forward(self, user):
        # if this user is already in the repeater queue don't add another one
        if queued_payload(user.domain, user.user_id):
            return False

        # If this user has already been forwarded without any changes, then
        # don't send it to BETS again
        successful_records = user.user_data.get('BETS_user_repeat_record_ids')
        if successful_records:
            latest_record_id = successful_records.split(" ")[-1]
            latest_record = RepeatRecord.get(latest_record_id)
            previous_payload = latest_record.attempts[-1].info if latest_record.attempts else "{}"
            try:
                previous_payload_json = json.loads(previous_payload)
                current_payload = get_bets_user_json(user.domain, user)
                del previous_payload_json['user_data']['id_device_number']
                del previous_payload_json['user_data']['id_device_body']
                del current_payload['user_data']['id_device_number']
                del current_payload['user_data']['id_device_body']
                if current_payload == previous_payload_json:
                    return False
            except (TypeError, ValueError):
                pass

        return (user.user_data.get('user_level', None) == 'real'
                and any(self._is_relevant_location(loc)
                        for loc in user.get_sql_locations(self.domain)))


class BETSLocationRepeater(BETSRepeaterMixin, LocationRepeater):
    friendly_name = _("BETS - Forward Locations")
    payload_generator_classes = (BETSLocationPayloadGenerator,)
    location_types_to_forward = (
        'ctd',
            'sto',
                'cto',
                    'dto',
                        'tu',
                        'plc',
                        'pcp',
                        'pcc',
                        'pac',
    )

    def get_attempt_info(self, repeat_record):
        """Store the payload as extra information
        """
        return six.text_type(self.get_payload(repeat_record))

    def allowed_to_forward(self, location):
        # if this location is already in the repeater queue, don't forward again
        if queued_payload(location.domain, location.location_id):
            return False

        # If this location has already been forwarded without any changes, then
        # don't send it to BETS again
        successful_records = location.metadata.get('BETS_location_repeat_record_ids')
        if successful_records:
            latest_record_id = successful_records.split(" ")[-1]
            latest_record = RepeatRecord.get(latest_record_id)
            previous_payload = latest_record.attempts[-1].info if latest_record.attempts else "{}"
            try:
                previous_payload_json = json.loads(previous_payload)
                current_payload = get_bets_location_json(location)
                if current_payload == previous_payload_json:
                    return False
            except (TypeError, ValueError):
                pass

        return (location.metadata.get('is_test') != "yes"
                and location.location_type.code in self.location_types_to_forward)


class BETSBeneficiaryRepeater(BaseBETSRepeater):
    friendly_name = _("BETS - Patient (beneficiary) registration and update")
    payload_generator_classes = (BETSBeneficiaryPayloadGenerator,)
    properties_we_care_about = (
        'phone_number',
        'current_address_district_choice',
        'current_address_state_choice',
        'current_episode_type',
    )

    def allowed_to_forward(self, person_case):
        return (person_case.type == CASE_TYPE_PERSON
                and person_case.get_case_property(ENROLLED_IN_PRIVATE) == 'true'
                and person_case.get_case_property('current_episode_type') == 'confirmed_tb'
                and is_valid_person_submission(person_case)
                and (case_was_created(person_case)
                     or case_properties_changed(person_case, self.properties_we_care_about)))


@receiver(case_post_save, sender=CommCareCaseSQL, dispatch_uid="create_BETS_case_repeat_records")
def create_BETS_repeat_records(sender, case, **kwargs):
    create_repeat_records(ChemistBETSVoucherRepeater, case)
    create_repeat_records(LabBETSVoucherRepeater, case)
    create_repeat_records(BETS180TreatmentRepeater, case)
    create_repeat_records(BETSDrugRefillRepeater, case)
    create_repeat_records(BETSSuccessfulTreatmentRepeater, case)
    create_repeat_records(BETSDiagnosisAndNotificationRepeater, case)
    create_repeat_records(BETSAYUSHReferralRepeater, case)
    create_repeat_records(BETSBeneficiaryRepeater, case)


@receiver(post_save, sender=SQLLocation, dispatch_uid="create_BETS_location_repeat_records")
def create_BETS_location_repeat_records(sender, raw=False, **kwargs):
    if raw:
        return
    create_repeat_records(BETSLocationRepeater, kwargs['instance'])


@receiver(commcare_user_post_save, dispatch_uid="create_BETS_user_repeat_records")
def create_BETS_user_repeat_records(sender, couch_user, **kwargs):
    create_repeat_records(BETSUserRepeater, couch_user)
