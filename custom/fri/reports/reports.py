import pytz
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.util import format_datatables_data
from custom.fri.models import PROFILE_A, PROFILE_B, PROFILE_C, PROFILE_D, PROFILE_E, PROFILE_F, PROFILE_G, PROFILE_DESC, FRISMSLog
from custom.fri.reports.filters import InteractiveParticipantFilter, RiskProfileFilter
from custom.fri.api import get_message_bank, add_metadata
from corehq.apps.sms.models import INCOMING, OUTGOING
from dimagi.utils.parsing import json_format_datetime
from casexml.apps.case.models import CommCareCase
from corehq.apps.users.models import CouchUser
from dimagi.utils.timezones import utils as tz_utils
from custom.fri.api import get_interactive_participants
from django.core.urlresolvers import reverse
from corehq.apps.reports.dispatcher import CustomProjectReportDispatcher

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
        case = CommCareCase.get(case_id)
        if case.domain != self.domain:
            return []
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

class MessageReport(CustomProjectReport, GenericTabularReport, DatespanMixin):
    name = ugettext_noop('Message Report')
    slug = 'fri_message_report'
    fields = [DatespanMixin.datespan_field]
    exportable = True
    emailable = False

    @property
    def headers(self):
        header = DataTablesHeader(
            DataTablesColumn(_("Timestamp")),
            DataTablesColumn(_("Counterparty")),
            DataTablesColumn(_("Phone Number")),
            DataTablesColumn(_("Sender")),
            DataTablesColumn(_("Direction")),
            DataTablesColumn(_("Message")),
            DataTablesColumn(_("Message Unique ID")),
            DataTablesColumn(_("Risk Profile")),
            DataTablesColumn(_("Theoretical Construct")),
        )
        header.custom_sort = [[0, "desc"]]
        return header

    @property
    def rows(self):
        startdate = json_format_datetime(self.datespan.startdate_utc)
        enddate = json_format_datetime(self.datespan.enddate_utc)
        data = FRISMSLog.view("sms/by_domain",
                              startkey=[self.domain, "SMSLog", startdate],
                              endkey=[self.domain, "SMSLog", enddate],
                              include_docs=True,
                              reduce=False).all()
        result = []
        username_map = {} # Store the results of username lookups for faster loading
        direction_map = {
            INCOMING: _("Incoming"),
            OUTGOING: _("Outgoing"),
        }
        message_bank_messages = get_message_bank(self.domain, for_comparing=True)

        for message in data:
            # Add metadata from the message bank if it has not been added already
            if (message.direction == OUTGOING) and (not message.message_bank_lookup_completed):
                add_metadata(message, message_bank_messages)

            # Lookup the message recipient
            recipient_id = message.couch_recipient
            if recipient_id in [None, ""]:
                username = "-"
            elif recipient_id in username_map:
                username = username_map.get(recipient_id)
            else:
                username = "-"
                try:
                    if message.couch_recipient_doc_type == "CommCareCase":
                        username = CommCareCase.get(recipient_id).name
                    else:
                        username = CouchUser.get_by_user_id(recipient_id).username
                except Exception:
                    pass
                username_map[recipient_id] = username

            # Lookup the sender
            if message.direction == OUTGOING:
                if message.chat_user_id in [None, ""]:
                    sender = _("System")
                else:
                    sender = "-"
                    if message.chat_user_id in username_map:
                        sender = username_map[message.chat_user_id]
                    else:
                        try:
                            sender = CouchUser.get_by_user_id(message.chat_user_id).username
                        except Exception:
                            pass
                        username_map[message.chat_user_id] = sender
            else:
                sender = "-"

            timestamp = tz_utils.adjust_datetime_to_timezone(message.date, pytz.utc.zone, self.timezone.zone)
            result.append([
                self._fmt_timestamp(timestamp),
                self._fmt(username),
                self._fmt(message.phone_number),
                self._fmt(sender),
                self._fmt(direction_map.get(message.direction,"-")),
                self._fmt(message.text),
                self._fmt(message.fri_id or "-"),
                self._fmt(message.risk_profile or "-"),
                self._fmt(message.theory_code or "-"),
            ])
        return result

    def _fmt(self, val):
        return format_datatables_data(val, val)

    def _fmt_timestamp(self, timestamp):
        return self.table_cell(
            timestamp,
            timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        )

class PHEDashboardReport(CustomProjectReport, GenericTabularReport):
    name = ugettext_noop("PHE Dashboard")
    slug = "fri_phe_dashboard"
    description = ugettext_noop("Displays a list of active, arm A, participants.")
    emailable = False
    exportable = False

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Participant")),
            DataTablesColumn(_("Open Chat Window")),
            DataTablesColumn(_("Open Message Bank")),
        )

    @property
    def rows(self):
        result = []
        cases = get_interactive_participants(self.domain)
        for case in cases:
            result.append([
                self._fmt(case.name),
                self._fmt_chat_link(case.get_id),
                self._fmt_message_bank_link(case.get_id),
            ])
        return result

    def _fmt(self, val):
        return format_datatables_data(val, val)

    def _fmt_chat_link(self, case_id):
        url = reverse("sms_chat", args=[self.domain, case_id])
        return self.table_cell(
            case_id,
            """<span class="btn btn-primary" onClick="window.open('%s', '_blank', 'location=no,menubar=no,scrollbars=no,status=no,toolbar=no,height=400,width=400');">%s</span>""" % (url, _("Open Chat Window")),
        )

    def _fmt_message_bank_link(self, case_id):
        url = reverse(CustomProjectReportDispatcher.name(), args=[self.domain, MessageBankReport.slug])
        url = "%s?participant=%s" % (url, case_id)
        return self.table_cell(
            case_id,
            """<span class="btn btn-primary" onClick="window.open('%s', '_blank');">%s</span>""" % (url, _("Open Message Bank")),
        )

