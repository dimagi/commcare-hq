from dateutil.parser import parse
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from casexml.apps.case.signals import case_post_save
from corehq.apps.locations.models import SQLLocation
from corehq.apps.repeaters.models import CaseRepeater, LocationRepeater
from corehq.apps.repeaters.signals import create_repeat_records
from corehq.form_processor.models import CommCareCaseSQL
from corehq.toggles import BETS_INTEGRATION
from corehq.util import reverse
from custom.enikshay.const import ENROLLED_IN_PRIVATE, PRESCRIPTION_TOTAL_DAYS_THRESHOLD
from custom.enikshay.integrations.bets.const import TREATMENT_180_EVENT, DRUG_REFILL_EVENT, SUCCESSFUL_TREATMENT_EVENT, \
    DIAGNOSIS_AND_NOTIFICATION_EVENT, AYUSH_REFERRAL_EVENT, CHEMIST_VOUCHER_EVENT, LAB_VOUCHER_EVENT, \
    TOTAL_DAY_THRESHOLDS
from custom.enikshay.integrations.bets.repeater_generators import \
    BETS180TreatmentPayloadGenerator, LabBETSVoucherPayloadGenerator, \
    ChemistBETSVoucherPayloadGenerator, BETSAYUSHReferralPayloadGenerator, \
    BETSDiagnosisAndNotificationPayloadGenerator, BETSSuccessfulTreatmentPayloadGenerator, \
    BETSDrugRefillPayloadGenerator, BETSLocationPayloadGenerator
from custom.enikshay.integrations.utils import case_properties_changed, is_valid_episode_submission, \
    is_valid_voucher_submission, is_valid_archived_submission, is_valid_person_submission, \
    case_was_created


class BaseBETSRepeater(CaseRepeater):
    class Meta(object):
        app_label = 'repeaters'

    @classmethod
    def available_for_domain(cls, domain):
        return BETS_INTEGRATION.enabled(domain)

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
    def _property_as_date(properties, property_name):
        """
        Parse the given value of the given property_name in the given property dict as a date.
        If the property is not a date, return None
        """
        try:
            return parse(properties.get(property_name, "nope"))
        except ValueError:
            return None

    @staticmethod
    def prescription_total_days_threshold_in_trigger_state(episode_case_properties, n):
        threshold_case_prop = BETSDrugRefillRepeater._get_threshold_case_prop(n)
        return bool(
            BETSDrugRefillRepeater._property_as_date(episode_case_properties, threshold_case_prop)
            and episode_case_properties.get("event_{}_{}".format(DRUG_REFILL_EVENT, n)) != "sent"
        )

    def allowed_to_forward(self, episode_case):
        if not self.case_types_and_users_allowed(episode_case):
            return False

        episode_case_properties = episode_case.dynamic_case_properties()
        trigger_by_threshold = {}  # threshold -> boolean
        threshold_prop_values_by_threshold = {}  # threshold -> date

        for n in TOTAL_DAY_THRESHOLDS:
            threshold_case_prop = self._get_threshold_case_prop(n)
            threshold_prop_values_by_threshold[n] = self._property_as_date(
                episode_case_properties, threshold_case_prop
            )
            trigger_for_n = bool(
                self.prescription_total_days_threshold_in_trigger_state(episode_case_properties, n)
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

        case_properties = episode_case.dynamic_case_properties()
        prescription_total_days = _cast_to_int(case_properties.get("prescription_total_days", 0))
        treatment_options = case_properties.get("treatment_options")
        if treatment_options == "fdc":
            meets_days_threshold = prescription_total_days >= 168
        else:
            meets_days_threshold = prescription_total_days >= 180

        enrolled_in_private_sector = case_properties.get(ENROLLED_IN_PRIVATE) == 'true'
        not_sent = case_properties.get("event_{}".format(SUCCESSFUL_TREATMENT_EVENT)) != "sent"
        return (
            meets_days_threshold
            and case_properties.get("treatment_outcome") in ("cured", "treatment_completed")
            and case_properties_changed(episode_case, ['prescription_total_days', "treatment_outcome"])
            and not_sent
            and enrolled_in_private_sector
            and is_valid_archived_submission(episode_case)
        )


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
            and case_properties_changed(episode_case, ['bets_first_prescription_voucher_redeemed'])
            and not_sent
            and enrolled_in_private_sector
            and is_valid_episode_submission(episode_case)
        )


class BETSAYUSHReferralRepeater(BaseBETSRepeater):
    friendly_name = _("BETS - Providers: For diagnosis and notification of TB case (episode case type)")

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
            and case_properties_changed(episode_case, ['bets_first_prescription_voucher_redeemed'])
            and case_properties.get("created_by_user_type") == "pac"
            and not_sent
            and enrolled_in_private_sector
            and is_valid_episode_submission(episode_case)
        )


class BETSLocationRepeater(LocationRepeater):
    friendly_name = _("Forward locations to BETS")
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

    @classmethod
    def available_for_domain(cls, domain):
        return BETS_INTEGRATION.enabled(domain)

    def allowed_to_forward(self, location):
        return (location.metadata.get('is_test') != "yes"
                and location.location_type.code in self.location_types_to_forward)

    class Meta(object):
        app_label = 'repeaters'


class BETSBeneficiaryRepeater(BaseBETSRepeater):
    friendly_name = _("BETS - Beneficiary creation and update")
    properties_we_care_about = (
        'phone_number',
        'current_address_district_choice',
        'current_address_state_choice',
    )

    def allowed_to_forward(self, person_case):
        if not (self._allowed_case_type(person_case) and self._allowed_user(person_case)):
            return False

        return (is_valid_person_submission(person_case)
                and person_case.get_case_property(ENROLLED_IN_PRIVATE) == 'true'
                and (case_was_created(person_case)
                     or case_properties_changed(person_case, self.properties_we_care_about)))


def create_BETS_repeat_records(sender, case, **kwargs):
    create_repeat_records(ChemistBETSVoucherRepeater, case)
    create_repeat_records(LabBETSVoucherRepeater, case)
    create_repeat_records(BETS180TreatmentRepeater, case)
    create_repeat_records(BETSDrugRefillRepeater, case)
    create_repeat_records(BETSSuccessfulTreatmentRepeater, case)
    create_repeat_records(BETSDiagnosisAndNotificationRepeater, case)
    create_repeat_records(BETSAYUSHReferralRepeater, case)
    create_repeat_records(BETSBeneficiaryRepeater, case)

case_post_save.connect(create_BETS_repeat_records, CommCareCaseSQL)


@receiver(post_save, sender=SQLLocation, dispatch_uid="create_bets_location_repeat_records")
def create_bets_location_repeat_records(sender, raw=False, **kwargs):
    if raw:
        return
    create_repeat_records(BETSLocationRepeater, kwargs['instance'])
