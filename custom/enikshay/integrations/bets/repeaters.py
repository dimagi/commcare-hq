from django.utils.translation import ugettext_lazy as _
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.apps.repeaters.models import CaseRepeater
from corehq.apps.repeaters.signals import create_repeat_records
from corehq.form_processor.models import CommCareCaseSQL
from corehq.toggles import BETS_INTEGRATION
from corehq.util import reverse
from custom.enikshay.case_utils import get_episode_case_from_voucher, get_prescription_vouchers_from_episode, \
    get_approved_prescription_vouchers_from_episode
from custom.enikshay.const import TREATMENT_180_EVENT, DRUG_REFILL_EVENT, SUCCESSFUL_TREATMENT_EVENT, \
    DIAGNOSIS_AND_NOTIFICATION_EVENT, AYUSH_REFERRAL_EVENT, VOUCHER_EVENT_ID
from custom.enikshay.integrations.utils import case_properties_changed


class BaseBETSRepeater(CaseRepeater):
    class Meta(object):
        app_label = 'repeaters'

    @classmethod
    def available_for_domain(cls, domain):
        return BETS_INTEGRATION.enabled(domain)

    def case_types_and_users_allowed(self, case):
        return self._allowed_case_type(case) and self._allowed_user(case)


class BETSVoucherRepeater(BaseBETSRepeater):
    """Forward a voucher to BETS
    Case Type: Voucher
    Trigger: When voucher.state transitions to "approved" or "partially_approved"
             and voucher.sent_to_bets != 'true'
    Side Effects:
        Success: voucher.event_{EVENT_ID} = "true" and voucher.bets_{EVENT_ID}_error = ''
        Error: voucher.bets_{EVENT_ID}_error = 'error message'
    """
    friendly_name = _("BETS - Voucher Forwarding (voucher case type)")

    @classmethod
    def get_custom_url(cls, domain):
        from custom.enikshay.integrations.bets.views import BETSVoucherRepeaterView
        return reverse(BETSVoucherRepeaterView.urlname, args=[domain])

    def allowed_to_forward(self, voucher_case):
        if not self.case_types_and_users_allowed(voucher_case):
            return False

        case_properties = voucher_case.dynamic_case_properties()
        approved = case_properties.get("state") == "approved"
        not_sent = case_properties.get("event_{}".format(VOUCHER_EVENT_ID)) != "sent"
        return (
            approved
            and not_sent
            and case_properties_changed(voucher_case, ['state'])
        )


def create_case_repeat_records(sender, case, **kwargs):
    create_repeat_records(BETSVoucherRepeater, case)

case_post_save.connect(create_case_repeat_records, CommCareCaseSQL)

# TODO: Remove this when eNikshay gets migrated to SQL
case_post_save.connect(create_case_repeat_records, CommCareCase)
