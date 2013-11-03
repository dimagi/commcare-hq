import pytz
import logging
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.util import format_datatables_data
from custom.fri.models import FRISMSLog
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

class FRIReport(CustomProjectReport, GenericTabularReport):
    _interactive_participants = None

    @property
    def interactive_participants(self):
        if self._interactive_participants is None:
            self._interactive_participants = get_interactive_participants(self.domain)
        return self._interactive_participants

class MessageBankReport(FRIReport):
    name = ugettext_noop("Message Bank")
    slug = "fri_message_bank"
    description = ugettext_noop("Displays the message bank.")
    emailable = False
    fields = (
        "custom.fri.reports.filters.RiskProfileFilter",
    )
    report_template_path = "fri/message_bank.html"
    show_all_rows = True

    @property
    def template_context(self):
        result = {
            "is_previewer" : self.request.couch_user.is_previewer(),
        }
        return result

    @property
    def risk_profile(self):
        return RiskProfileFilter.get_value(self.request, self.domain)

    @property
    def headers(self):
        cols = [
            DataTablesColumn(_("Message Text")),
            DataTablesColumn(_("Message ID")),
        ]
        for case in self.interactive_participants:
            header_text = case.get_case_property("name_and_pid")
            cols.append(DataTablesColumn(header_text))
        header = DataTablesHeader(*cols)
        header.custom_sort = [[1, "asc"]]
        return header

    @property
    def rows(self):
        risk_profile = self.risk_profile
        result = []
        message_bank_messages = get_message_bank(self.domain, for_comparing=True)
        data = {}
        for case in self.interactive_participants:
            data[case._id] = self.get_participant_message_counts(message_bank_messages, case)

        for entry in message_bank_messages:
            if risk_profile and risk_profile != entry["message"].risk_profile:
                continue
            row = [
                self._fmt(entry["message"].message),
                self._fmt(entry["message"].fri_id or "-"),
            ]
            for case in self.interactive_participants:
                row.append(self._fmt(data[case._id][entry["message"]._id]))
            result.append(row)
        return result

    def get_participant_messages(self, case):
        result = FRISMSLog.view("sms/by_recipient",
                                startkey=["CommCareCase", case._id, "SMSLog", OUTGOING],
                                endkey=["CommCareCase", case._id, "SMSLog", OUTGOING, {}],
                                reduce=False,
                                include_docs=True).all()
        return result

    def get_participant_message_counts(self, message_bank_messages, case):
        result = {}
        for entry in message_bank_messages:
            result[entry["message"]._id] = 0
        participant_messages = self.get_participant_messages(case)
        for sms in participant_messages:
            if sms.chat_user_id is not None:
                if not sms.message_bank_lookup_completed:
                    add_metadata(sms, message_bank_messages)
                if sms.message_bank_message_id in result:
                    result[sms.message_bank_message_id] += 1
        return result

    def _fmt(self, val):
        return format_datatables_data(val, val)

class MessageReport(FRIReport, DatespanMixin):
    name = ugettext_noop('Message Report')
    slug = 'fri_message_report'
    fields = [DatespanMixin.datespan_field]
    exportable = True
    emailable = False

    @property
    def headers(self):
        header = DataTablesHeader(
            DataTablesColumn(_("Message Text")),
            DataTablesColumn(_("Message ID")),
            DataTablesColumn(_("Timestamp")),
            DataTablesColumn(_("Participant ID")),
            DataTablesColumn(_("Originator")),
            DataTablesColumn(_("Direction")),
        )
        header.custom_sort = [[2, "desc"]]
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
                        username = CommCareCase.get(recipient_id).get_case_property("pid")
                    else:
                        user = CouchUser.get_by_user_id(recipient_id)
                        username = user.first_name or user.raw_username
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
                            user = CouchUser.get_by_user_id(message.chat_user_id)
                            sender = user.first_name or user.raw_username
                        except Exception:
                            pass
                        username_map[message.chat_user_id] = sender
            else:
                sender = "-"

            timestamp = tz_utils.adjust_datetime_to_timezone(message.date, pytz.utc.zone, self.timezone.zone)
            result.append([
                self._fmt(message.text),
                self._fmt(message.fri_id or "-"),
                self._fmt_timestamp(timestamp),
                self._fmt(username),
                self._fmt(sender if message.direction == OUTGOING else username),
                self._fmt(direction_map.get(message.direction,"-")),
            ])
        return result

    def _fmt(self, val):
        return format_datatables_data(val, val)

    def _fmt_timestamp(self, timestamp):
        return self.table_cell(
            timestamp,
            timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        )

class PHEDashboardReport(FRIReport):
    name = ugettext_noop("PHE Dashboard")
    slug = "fri_phe_dashboard"
    description = ugettext_noop("Displays a list of active, arm A, participants.")
    emailable = False
    exportable = False
    report_template_path = "fri/phe_dashboard.html"
    hide_filters = True

    @property
    def template_context(self):
        result = {
            "fri_message_bank_url" : reverse(CustomProjectReportDispatcher.name(), args=[self.domain, MessageBankReport.slug]),
            "fri_chat_actions" : [self._open_chat_action(case._id) for case in self.interactive_participants],
        }
        return result

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Participant")),
            DataTablesColumn(_("Open Chat Window")),
        )

    @property
    def rows(self):
        result = []
        cases = self.interactive_participants
        for case in cases:
            result.append([
                self._fmt(case.get_case_property("name_and_pid")),
                self._fmt_chat_link(case.get_id),
            ])
        return result

    def _fmt(self, val):
        return format_datatables_data(val, val)

    def _fmt_chat_link(self, case_id):
        return self.table_cell(
            case_id,
            """<span class="btn btn-primary" onClick="%s">%s</span>""" % (self._open_chat_action(case_id), _("Open Chat Window")),
        )

    def _open_chat_action(self, case_id):
        url = reverse("sms_chat", args=[self.domain, case_id])
        return "window.open('%s', '_blank', 'location=no,menubar=no,scrollbars=no,status=no,toolbar=no,height=400,width=400');" % url

