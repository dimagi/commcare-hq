from django.utils.translation import ugettext_lazy as _
from casexml.apps.case.signals import case_post_save
from dimagi.utils.decorators.memoized import memoized

from corehq.apps.repeaters.models import CaseRepeater, Repeater
from corehq.apps.repeaters.signals import create_repeat_records
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.signals import commcare_user_post_save
from corehq.form_processor.models import CommCareCaseSQL
from corehq.toggles import BETS_INTEGRATION
from corehq.util import reverse
from custom.enikshay.case_utils import (
    get_episode_case_from_voucher,
    get_approved_prescription_vouchers_from_episode,
)
from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.integrations.bets.const import TREATMENT_180_EVENT, DRUG_REFILL_EVENT, SUCCESSFUL_TREATMENT_EVENT, \
    DIAGNOSIS_AND_NOTIFICATION_EVENT, AYUSH_REFERRAL_EVENT, CHEMIST_VOUCHER_EVENT, LAB_VOUCHER_EVENT
from custom.enikshay.integrations.utils import case_properties_changed, is_valid_episode_submission, \
    is_valid_voucher_submission, is_valid_archived_submission


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

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.bets.views import ChemistBETSVoucherRepeaterView
        return reverse(ChemistBETSVoucherRepeaterView.urlname, args=[domain])


class LabBETSVoucherRepeater(BaseBETSVoucherRepeater):
    friendly_name = _("BETS - Lab Voucher Forwarding (voucher case type)")
    event_id = LAB_VOUCHER_EVENT
    voucher_type = "test"

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.bets.views import LabBETSVoucherRepeaterView
        return reverse(LabBETSVoucherRepeaterView.urlname, args=[domain])


class BETS180TreatmentRepeater(BaseBETSRepeater):
    friendly_name = _(
        "BETS - MBBS+ Providers: 180 days of private OR govt. "
        "FDCs with treatment outcome reported (episode case type)"
    )

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.bets.views import BETS180TreatmentRepeaterView
        return reverse(BETS180TreatmentRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, episode_case):
        if not self.case_types_and_users_allowed(episode_case):
            return False

        case_properties = episode_case.dynamic_case_properties()
        treatment_outcome = case_properties.get('treatment_outcome', None)
        treatment_outcome_transitioned = case_properties_changed(episode_case, ['treatment_outcome'])
        enrolled_in_private_sector = case_properties.get(ENROLLED_IN_PRIVATE) == 'true'
        episode_has_outcome = treatment_outcome and (treatment_outcome != 'not_evaluated')
        adherence_total_doses_taken = case_properties.get('adherence_total_doses_taken', "0")
        try:
            adherence_total_doses_taken = int(adherence_total_doses_taken)
        except ValueError:
            adherence_total_doses_taken = 0

        not_sent = case_properties.get("event_{}".format(TREATMENT_180_EVENT)) != "sent"
        return (
            episode_has_outcome
            and treatment_outcome_transitioned
            and not_sent
            and adherence_total_doses_taken >= 180
            and enrolled_in_private_sector
            and is_valid_episode_submission(episode_case)
        )


class BETSDrugRefillRepeater(BaseBETSRepeater):
    friendly_name = _("BETS - Patients: Cash transfer on subsequent drug refill (voucher case type)")

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.bets.views import BETSDrugRefillRepeaterView
        return reverse(BETSDrugRefillRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, voucher_case):
        if not self.case_types_and_users_allowed(voucher_case):
            return False

        voucher_case_properties = voucher_case.dynamic_case_properties()
        episode = get_episode_case_from_voucher(voucher_case.domain, voucher_case.case_id)
        episode_case_properties = episode.dynamic_case_properties()

        def _get_voucher_count():
            # This is an expensive operation, so only call this function if all other conditions are true.
            voucher_count = episode_case_properties.get('approved_voucher_count', 0)
            if voucher_count < 2:
                voucher_count = len(
                    get_approved_prescription_vouchers_from_episode(episode.domain, episode.case_id)
                )
            return voucher_count

        not_sent = voucher_case_properties.get("event_{}".format(DRUG_REFILL_EVENT)) != "sent"

        return (
            # TODO: Confirm state == "fulfilled"
            voucher_case_properties.get("state") == "fulfilled"
            and voucher_case_properties.get("type") == "prescription"
            and not_sent
            and case_properties_changed(voucher_case, ['state'])
            and is_valid_voucher_submission(voucher_case)
            and _get_voucher_count() >= 2
        )


class BETSSuccessfulTreatmentRepeater(BaseBETSRepeater):
    friendly_name = _("BETS - Patients: Cash transfer on successful treatment completion (episode case type)")

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.bets.views import BETSSuccessfulTreatmentRepeaterView
        return reverse(BETSSuccessfulTreatmentRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, episode_case):
        if not self.case_types_and_users_allowed(episode_case):
            return False

        case_properties = episode_case.dynamic_case_properties()
        not_sent = case_properties.get("event_{}".format(SUCCESSFUL_TREATMENT_EVENT)) != "sent"
        enrolled_in_private_sector = case_properties.get(ENROLLED_IN_PRIVATE) == 'true'
        return (
            case_properties.get("treatment_outcome") in ("cured", "treatment_completed")
            and case_properties_changed(episode_case, ["treatment_outcome"])
            and not_sent
            and enrolled_in_private_sector
            and is_valid_archived_submission(episode_case)
        )


class BETSDiagnosisAndNotificationRepeater(BaseBETSRepeater):
    friendly_name = _("BETS - Providers: For diagnosis and notification of TB case (episode case type)")

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
            case_properties.get("pending_registration") == "no"
            and case_properties.get("nikshay_registered") == 'true'
            and case_properties_changed(episode_case, ['nikshay_registered'])
            and not_sent
            and enrolled_in_private_sector
            and is_valid_episode_submission(episode_case)
        )


class BETSAYUSHReferralRepeater(BaseBETSRepeater):
    friendly_name = _("BETS - Providers: For diagnosis and notification of TB case (episode case type)")

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.bets.views import BETSAYUSHReferralRepeaterView
        return reverse(BETSAYUSHReferralRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, episode_case):
        if not self.case_types_and_users_allowed(episode_case):
            return False

        case_properties = episode_case.dynamic_case_properties()
        presumptive_referral_by_ayush = (
            case_properties.get("presumptive_referral_by_ayush")
            and case_properties.get("presumptive_referral_by_ayush") != "false"
        )
        not_sent = case_properties.get("event_{}".format(AYUSH_REFERRAL_EVENT)) != "sent"
        enrolled_in_private_sector = case_properties.get(ENROLLED_IN_PRIVATE) == 'true'
        return (
            presumptive_referral_by_ayush
            and case_properties.get("nikshay_registered") == 'true'
            and case_properties_changed(episode_case, ['nikshay_registered'])
            and not_sent
            and enrolled_in_private_sector
            and is_valid_episode_submission(episode_case)
        )


def create_case_repeat_records(sender, case, **kwargs):
    create_repeat_records(ChemistBETSVoucherRepeater, case)
    create_repeat_records(LabBETSVoucherRepeater, case)
    create_repeat_records(BETS180TreatmentRepeater, case)
    create_repeat_records(BETSDrugRefillRepeater, case)
    create_repeat_records(BETSSuccessfulTreatmentRepeater, case)
    create_repeat_records(BETSDiagnosisAndNotificationRepeater, case)
    create_repeat_records(BETSAYUSHReferralRepeater, case)

case_post_save.connect(create_case_repeat_records, CommCareCaseSQL)


class BETSUserRepeater(Repeater):
    friendly_name = _("Forward Users")

    class Meta(object):
        app_label = 'repeaters'

    @memoized
    def payload_doc(self, repeat_record):
        return CommCareUser.get(repeat_record.payload_id)

    @classmethod
    def available_for_domain(cls, domain):
        return BETS_INTEGRATION.enabled(domain)

    def __unicode__(self):
        return "forwarding users to: %s" % self.url


def create_user_repeat_records(sender, couch_user, **kwargs):
    create_repeat_records(BETSUserRepeater, couch_user)


commcare_user_post_save.connect(create_user_repeat_records)
