from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.util import format_datatables_data
from custom.fri.models import PROFILE_A, PROFILE_B, PROFILE_C, PROFILE_D, PROFILE_E, PROFILE_F, PROFILE_G, PROFILE_DESC, FRISMSLog
from custom.fri.reports.filters import InteractiveParticipantFilter, RiskProfileFilter
from custom.fri.api import get_message_bank, add_metadata
from corehq.apps.sms.models import OUTGOING

class MessageBankReport(CustomProjectReport, GenericTabularReport):
    name = ugettext_noop("Message Bank")
    slug = "fri_message_bank"
    description = ugettext_noop("Displays usage of the message bank for a given participant.")
    emailable = False
    fields = (
        "custom.fri.reports.filters.InteractiveParticipantFilter",
        "custom.fri.reports.filters.RiskProfileFilter",
    )

    @property
    def risk_profile(self):
        return RiskProfileFilter.get_value(self.request, self.domain)

    @property
    def case_id(self):
        return InteractiveParticipantFilter.get_value(self.request, self.domain)

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Message Text")),
            DataTablesColumn(_("Count")),
            DataTablesColumn(_("Risk Profile")),
        )

    @property
    def rows(self):
        case_id = self.case_id
        risk_profile = self.risk_profile
        if case_id:
            intermediate_result = {}
            message_bank_messages = get_message_bank(self.domain, for_comparing=True)
            for entry in message_bank_messages:
                intermediate_result[entry["message"]._id] = {
                    "message" : entry["message"].message,
                    "count" : 0,
                    "risk_profile_code" : entry["message"].risk_profile,
                    "risk_profile_desc" : PROFILE_DESC.get(entry["message"].risk_profile, ""),
                }

            participant_messages = FRISMSLog.view("sms/by_recipient",
                                                  startkey=["CommCareCase", case_id, "SMSLog", OUTGOING],
                                                  endkey=["CommCareCase", case_id, "SMSLog", OUTGOING, {}],
                                                  reduce=False,
                                                  include_docs=True).all()
            for sms in participant_messages:
                if sms.chat_user_id is not None:
                    if not sms.message_bank_lookup_completed:
                        add_metadata(sms, message_bank_messages)
                    if sms.message_bank_message_id in intermediate_result:
                        intermediate_result[sms.message_bank_message_id]["count"] += 1
            result = []
            for key, value in intermediate_result.items():
                if risk_profile and (risk_profile != value["risk_profile_code"]):
                    continue
                result.append([
                    self._fmt(value["message"]),
                    self._fmt(value["count"]),
                    self._fmt(value["risk_profile_desc"]),
                ])
            return result
        else:
            return []

    def _fmt(self, val):
        return format_datatables_data(val, val)

