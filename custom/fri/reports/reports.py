import pytz
import logging
import cgi
from datetime import datetime, time, timedelta
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from corehq.apps.domain.models import Domain
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.datatables import (
    DataTablesColumn,
    DataTablesHeader,
    DTSortType,
)
from corehq.apps.reports.util import format_datatables_data
from corehq.util.timezones.conversions import ServerTime, UserTime
from custom.fri.models import FRISMSLog, PROFILE_DESC
from custom.fri.reports.filters import (InteractiveParticipantFilter,
    RiskProfileFilter, SurveyDateSelector)
from custom.fri.api import get_message_bank, add_metadata, get_date
from corehq.apps.sms.models import INCOMING, OUTGOING
from dimagi.utils.parsing import json_format_datetime
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xform import CaseDbCache
from corehq.apps.users.models import CouchUser, UserCache
from corehq.util.timezones import utils as tz_utils
from custom.fri.api import get_interactive_participants, get_valid_date_range
from django.core.urlresolvers import reverse
from corehq.apps.reports.dispatcher import CustomProjectReportDispatcher
from dateutil.parser import parse

RESPONSE_NOT_APPLICABLE = 1
NO_RESPONSE = 2

class FRIReport(CustomProjectReport, GenericTabularReport):
    _interactive_participants = None
    _domain_obj = None

    @property
    def timezone(self):
        return pytz.timezone(self.domain_obj.default_timezone)

    @property
    def domain_obj(self):
        if not self._domain_obj:
            self._domain_obj = Domain.get_by_name(self.domain, strict=True)
        return self._domain_obj

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
            DataTablesColumn(_("Risk Profile")),
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
            msg_risk_profile = entry["message"].risk_profile
            if risk_profile and risk_profile != msg_risk_profile:
                continue
            msg_risk_profile_desc = None
            if msg_risk_profile:
                msg_risk_profile_desc = PROFILE_DESC.get(msg_risk_profile)
            msg_risk_profile_desc = msg_risk_profile_desc or "-"
            row = [
                self._fmt(entry["message"].message),
                self._fmt2(entry["message"].fri_id, msg_risk_profile_desc),
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
            if sms.xforms_session_couch_id is None and sms.direction == OUTGOING:
                if not sms.fri_message_bank_lookup_completed:
                    add_metadata(sms, message_bank_messages)
                if sms.fri_message_bank_message_id in result:
                    result[sms.fri_message_bank_message_id] += 1
        return result

    def _fmt(self, val):
        return format_datatables_data(val, val)

    def _fmt2(self, val1, val2):
        val1 = cgi.escape(val1, True)
        val2 = cgi.escape(val2, True)
        return self.table_cell(val1, '<span style="display: none;">%s</span><span>%s</span>' % (val1, val2))

class MessageReport(FRIReport, DatespanMixin):
    name = ugettext_noop('Message Report')
    slug = 'fri_message_report'
    fields = [
        DatespanMixin.datespan_field,
        "custom.fri.reports.fields.ShowOnlySurveyTraffic",
    ]
    exportable = True
    emailable = False

    @property
    def headers(self):
        header = DataTablesHeader(
            DataTablesColumn(_("Participant ID")),
            DataTablesColumn(_("Study Arm")),
            DataTablesColumn(_("Originator")),
            DataTablesColumn(_("Timestamp")),
            DataTablesColumn(_("Message Text")),
            DataTablesColumn(_("Message ID")),
            DataTablesColumn(_("Direction")),
        )
        header.custom_sort = [[1, "asc"],[0, "asc"],[3, "asc"]]
        return header

    def _case_name(self, contact, reverse=False):
        first_name = contact.get_case_property("first_name") or ""
        pid = contact.get_case_property("pid") or ""
        if first_name or pid:
            if reverse:
                return "%s %s" % (pid, first_name)
            else:
                return "%s %s" % (first_name, pid)
        else:
            return "-"

    def _user_name(self, contact):
        return contact.first_name or contact.raw_username

    def _participant_id(self, contact):
        if contact and contact.doc_type == "CommCareCase":
            return self._case_name(contact, True)
        else:
            return "-"

    def _originator(self, message, recipient, sender):
        if message.direction == INCOMING:
            if recipient:
                if recipient.doc_type == "CommCareCase":
                    return self._case_name(recipient)
                else:
                    return self._user_name(recipient)
            else:
                return "-"
        else:
            if sender:
                if sender.doc_type == "CommCareCase":
                    return self._case_name(sender)
                else:
                    return self._user_name(sender)
            else:
                return _("System")

    def show_only_survey_traffic(self):
        value = self.request.GET.get("show_only_survey_traffic", None)
        return value == "on"

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
        direction_map = {
            INCOMING: _("Incoming"),
            OUTGOING: _("Outgoing"),
        }
        message_bank_messages = get_message_bank(self.domain, for_comparing=True)

        case_cache = CaseDbCache(domain=self.domain, strip_history=False, deleted_ok=True)
        user_cache = UserCache()

        show_only_survey_traffic = self.show_only_survey_traffic()

        for message in data:
            if message.direction == OUTGOING and not message.processed:
                continue
            if show_only_survey_traffic and message.xforms_session_couch_id is None:
                continue
            # Add metadata from the message bank if it has not been added already
            if (message.direction == OUTGOING) and (not message.fri_message_bank_lookup_completed):
                add_metadata(message, message_bank_messages)

            if message.couch_recipient_doc_type == "CommCareCase":
                recipient = case_cache.get(message.couch_recipient)
            else:
                recipient = user_cache.get(message.couch_recipient)

            if message.chat_user_id:
                sender = user_cache.get(message.chat_user_id)
            else:
                sender = None

            study_arm = None
            if message.couch_recipient_doc_type == "CommCareCase":
                study_arm = case_cache.get(message.couch_recipient).get_case_property("study_arm")

            timestamp = ServerTime(message.date).user_time(self.domain_obj.default_timezone).done()
            result.append([
                self._fmt(self._participant_id(recipient)),
                self._fmt(study_arm or "-"),
                self._fmt(self._originator(message, recipient, sender)),
                self._fmt_timestamp(timestamp),
                self._fmt(message.text),
                self._fmt(message.fri_id or "-"),
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
            DataTablesColumn(_("Last Day of PTS"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Open Chat Window")),
        )

    @property
    def rows(self):
        result = []
        cases = self.interactive_participants
        for case in cases:
            start_date, end_date = get_valid_date_range(case)
            # end_date will never be None because of how we get_interactive_participants
            result.append([
                self._fmt(case.get_case_property("name_and_pid")),
                self._fmt_date(end_date),
                self._fmt_chat_link(case.get_id),
            ])
        return result

    def _fmt(self, val):
        return format_datatables_data(val, val)

    def _fmt_date(self, val):
        date_as_num = int(val.strftime("%Y%m%d"))
        return format_datatables_data(val.strftime("%m/%d/%Y"), date_as_num)

    def _fmt_chat_link(self, case_id):
        return self.table_cell(
            case_id,
            """<span class="btn btn-primary" onClick="%s">%s</span>""" % (self._open_chat_action(case_id), _("Open Chat Window")),
        )

    def _open_chat_action(self, case_id):
        url = reverse("sms_chat", args=[self.domain, case_id])
        return "window.open('%s', '_blank', 'location=no,menubar=no,scrollbars=no,status=no,toolbar=no,height=400,width=400');" % url

class SurveyResponsesReport(FRIReport):
    name = ugettext_noop("Survey Responses")
    slug = "fri_survey_responses"
    description = ugettext_noop("Shows information pertaining to survey responses.")
    emailable = False
    fields = [
        "custom.fri.reports.filters.SurveyDateSelector",
    ]

    @property
    def survey_report_date(self):
        return SurveyDateSelector.get_value(self.request, self.domain)

    @property
    def headers(self):
        cols = [
            DataTablesColumn(_("PID")),
            DataTablesColumn(_("Name")),
            DataTablesColumn(_("Arm")),
            DataTablesColumn(_("Week 1")),
            DataTablesColumn(_("Week 2")),
            DataTablesColumn(_("Week 3")),
            DataTablesColumn(_("Week 4")),
            DataTablesColumn(_("Week 5")),
            DataTablesColumn(_("Week 6")),
            DataTablesColumn(_("Week 7")),
            DataTablesColumn(_("Week 8")),
        ]
        header = DataTablesHeader(*cols)
        header.custom_sort = [[0, "asc"]]
        return header

    @property
    def rows(self):
        participants = self.get_participants()
        result = []
        for case in participants:
            pid = case.get_case_property("pid")
            study_arm = case.get_case_property("study_arm")
            registration_date = get_date(case, "start_date")
            first_name = case.get_case_property("first_name") or ""
            if registration_date is None:
                continue
            first_survey_date = self.get_first_tuesday(registration_date)
            row = [
                self._fmt(pid),
                self._fmt(first_name),
                self._fmt(study_arm),
            ]
            for i in range(8):
                next_survey_date = first_survey_date + timedelta(days=7*i)
                response = self.get_first_survey_response(case, next_survey_date)
                if response == RESPONSE_NOT_APPLICABLE:
                    row.append(self._fmt("-"))
                elif response == NO_RESPONSE:
                    row.append(self._fmt(_("No Response")))
                else:
                    response_timestamp = ServerTime(response.date).user_time(self.domain_obj.default_timezone).done()
                    row.append(self._fmt_timestamp(response_timestamp))
            result.append(row)
        return result

    def get_first_tuesday(self, dt):
        while dt.weekday() != 1:
            dt = dt + timedelta(days=1)
        return dt

    def get_participants(self):
        result = CommCareCase.view("hqcase/types_by_domain",
                                   key=[self.domain, "participant"],
                                   include_docs=True,
                                   reduce=False).all()
        survey_report_date = parse(self.survey_report_date).date()

        def filter_function(case):
            registration_date = get_date(case, "start_date")
            if registration_date is None:
                return False
            first_tuesday = self.get_first_tuesday(registration_date)
            last_tuesday = first_tuesday + timedelta(days=49)
            return (survey_report_date >= first_tuesday and
                survey_report_date <= last_tuesday)

        result = filter(filter_function, result)
        return result

    def get_first_survey_response(self, case, dt):
        timestamp_start = datetime.combine(dt, time(20, 45))
        timestamp_start = UserTime(
            timestamp_start, self.domain_obj.default_timezone).server_time().done()
        timestamp_start = json_format_datetime(timestamp_start)

        timestamp_end = datetime.combine(dt + timedelta(days=1), time(11, 45))
        timestamp_end = UserTime(
            timestamp_end, self.domain_obj.default_timezone).server_time().done()
        if timestamp_end > datetime.utcnow():
            return RESPONSE_NOT_APPLICABLE
        timestamp_end = json_format_datetime(timestamp_end)

        all_inbound = FRISMSLog.view(
            "sms/by_recipient",
            startkey=["CommCareCase", case._id, "SMSLog", INCOMING, timestamp_start],
            endkey=["CommCareCase", case._id, "SMSLog", INCOMING, timestamp_end],
            reduce=False,
            include_docs=True
        ).all()

        survey_responses = filter(lambda s: s.xforms_session_couch_id is not None, all_inbound)
        if len(survey_responses) > 0:
            return survey_responses[0]
        else:
            return NO_RESPONSE

    def _fmt(self, val):
        return format_datatables_data(val, val)

    def _fmt_timestamp(self, timestamp):
        return self.table_cell(
            timestamp,
            timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        )

