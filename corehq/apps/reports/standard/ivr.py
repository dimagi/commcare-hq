import cgi

from django.conf import settings
from django.contrib import messages
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

from casexml.apps.case.models import CommCareCase

from corehq.apps.ivr.models import Call
from corehq.apps.reminders.util import get_form_name
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import (
    DatespanMixin,
    ProjectReport,
    ProjectReportParametersMixin,
)
from corehq.apps.reports.standard.sms import BaseCommConnectLogReport
from corehq.apps.reports.util import format_datatables_data
from corehq.apps.sms.models import (
    CALLBACK_MISSED,
    CALLBACK_PENDING,
    CALLBACK_RECEIVED,
    INCOMING,
    OUTGOING,
    ExpectedCallback,
)
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.apps.users.models import CouchUser
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.util.quickcache import quickcache
from corehq.util.timezones.conversions import ServerTime
from corehq.util.view_utils import absolute_reverse


@quickcache(['domain'], timeout=60 * 60)
def domain_has_any_calls(domain):
    return Call.objects.filter(domain=domain).count() > 0


@quickcache(['domain'], timeout=60 * 60)
def domain_has_any_expected_callbacks(domain):
    return ExpectedCallback.objects.filter(domain=domain).count() > 0


class CallReport(BaseCommConnectLogReport):
    """
    Displays all calls for the given domain and date range.
    """
    name = ugettext_noop('Call Log')
    slug = 'call_log'
    fields = ['corehq.apps.reports.filters.dates.DatespanFilter']
    exportable = True
    emailable = True

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return domain_has_any_calls(domain)

    @property
    def template_context(self):
        msg = """
        WARNING! This page will be deleted in early November 2019.
        If you rely on this report, please contact <a href='mailto:{}'>{}</a>
        to discuss as soon as possible.
        """.format(settings.SUPPORT_EMAIL, settings.SUPPORT_EMAIL)
        messages.add_message(self.request, messages.ERROR, msg, extra_tags="html")
        return super().template_context

    @property
    def headers(self):
        header_list = [
            DataTablesColumn(_("Timestamp")),
            DataTablesColumn(_("User Name")),
            DataTablesColumn(_("Phone Number")),
            DataTablesColumn(_("Direction")),
            DataTablesColumn(_("Form")),
            DataTablesColumn(_("View Submission")),
            DataTablesColumn(_("Answered")),
            DataTablesColumn(_("Duration")),
            DataTablesColumn(_("Error")),
            DataTablesColumn(_("Error Message")),
        ]

        if self.request.couch_user.is_previewer():
            header_list.append(DataTablesColumn(_("Gateway - Session Id")))

        header = DataTablesHeader(*header_list)
        header.custom_sort = [[0, 'desc']]

        return header

    @property
    def rows(self):
        data = Call.by_domain(
            self.domain,
            start_date=self.datespan.startdate_utc,
            end_date=self.datespan.enddate_utc
        ).order_by('date')
        result = []
        
        # Store the results of lookups for faster loading
        contact_cache = {}
        form_map = {}
        xforms_sessions = {}
        
        direction_map = {
            INCOMING: _("Incoming"),
            OUTGOING: _("Outgoing"),
        }
        
        # Retrieve message log options
        message_log_options = getattr(settings, "MESSAGE_LOG_OPTIONS", {})
        abbreviated_phone_number_domains = message_log_options.get("abbreviated_phone_number_domains", [])
        abbreviate_phone_number = (self.domain in abbreviated_phone_number_domains)
        
        for call in data:
            doc_info = self.get_recipient_info(self.domain, call.couch_recipient_doc_type,
                call.couch_recipient, contact_cache)

            form_unique_id = call.form_unique_id
            if form_unique_id in [None, ""]:
                form_name = "-"
            elif form_unique_id in form_map:
                form_name = form_map.get(form_unique_id)
            else:
                form_name = get_form_name(form_unique_id)
                form_map[form_unique_id] = form_name
            
            phone_number = call.phone_number
            if abbreviate_phone_number and phone_number is not None:
                phone_number = phone_number[0:7] if phone_number[0:1] == "+" else phone_number[0:6]
            
            timestamp = ServerTime(call.date).user_time(self.timezone).done()
            
            if call.direction == INCOMING:
                answered = "-"
            else:
                answered = _("Yes") if call.answered else _("No")
            
            if call.xforms_session_id:
                xforms_sessions[call.xforms_session_id] = None
            
            row = [
                call.xforms_session_id,
                self._fmt_timestamp(timestamp),
                self._fmt_contact_link(call.couch_recipient, doc_info),
                self._fmt(phone_number),
                self._fmt(direction_map.get(call.direction, "-")),
                self._fmt(form_name),
                self._fmt("-"),
                self._fmt(answered),
                self._fmt(call.duration),
                self._fmt(_("Yes") if call.error else _("No")),
                self._fmt(cgi.escape(call.error_message) if call.error_message else None),
            ]
            
            if self.request.couch_user.is_previewer():
                row.append(self._fmt(call.gateway_session_id))
            
            result.append(row)

        all_session_ids = list(xforms_sessions)
        session_submission_map = dict(
            SQLXFormsSession.objects.filter(session_id__in=all_session_ids).values_list(
                'session_id', 'submission_id'
            )
        )
        xforms_sessions.update(session_submission_map)

        # Add into the final result the link to the submission based on the
        # outcome of the above lookups.
        final_result = []
        for row in result:
            final_row = row[1:]
            session_id = row[0]
            if session_id:
                submission_id = xforms_sessions[session_id]
                if submission_id:
                    final_row[5] = self._fmt_submission_link(submission_id)
            final_result.append(final_row)

        return final_result

    def _fmt_submission_link(self, submission_id):
        url = absolute_reverse("render_form_data", args=[self.domain, submission_id])
        display_text = _("View Submission")
        ret = self.table_cell(display_text, '<a href="%s">%s</a>' % (url, display_text))
        ret['raw'] = submission_id
        return ret


class ExpectedCallbackReport(ProjectReport, ProjectReportParametersMixin, GenericTabularReport, DatespanMixin):
    """
    Displays all expected callbacks for the given time period.
    """
    name = ugettext_noop('Expected Callbacks')
    slug = 'expected_callbacks'
    fields = ['corehq.apps.reports.filters.dates.DatespanFilter']
    exportable = True
    default_datespan_end_date_to_today = True

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return domain_has_any_expected_callbacks(domain)

    @property
    def template_context(self):
        msg = """
        WARNING! This page will be deleted in early November 2019.
        If you rely on this report, please contact <a href='mailto:{}'>{}</a>
        to discuss as soon as possible.
        """.format(settings.SUPPORT_EMAIL, settings.SUPPORT_EMAIL)
        messages.add_message(self.request, messages.ERROR, msg, extra_tags="html")
        ctxt = super().template_context

    @property
    def headers(self):
        header_list = [
            DataTablesColumn(_("Timestamp")),
            DataTablesColumn(_("Recipient Name")),
            DataTablesColumn(_("Status")),
        ]
        
        return DataTablesHeader(*header_list)
    
    @property
    def rows(self):
        data = ExpectedCallback.by_domain(
            self.domain,
            start_date=self.datespan.startdate_utc,
            end_date=self.datespan.enddate_utc
        ).order_by('date')
        result = []
        
        status_descriptions = {
            CALLBACK_PENDING: _("Pending"),
            CALLBACK_RECEIVED: _("Received"),
            CALLBACK_MISSED: _("Missed"),
        }
        
        # Store the results of lookups for faster loading
        username_map = {} 
        
        for event in data:
            recipient_id = event.couch_recipient
            if recipient_id in [None, ""]:
                username = "-"
            elif recipient_id in username_map:
                username = username_map.get(recipient_id)
            else:
                username = "-"
                try:
                    if event.couch_recipient_doc_type == "CommCareCase":
                        username = CommCareCase.get(recipient_id).name
                    else:
                        username = CouchUser.get_by_user_id(recipient_id).username
                except Exception:
                    pass
               
                username_map[recipient_id] = username
            
            timestamp = ServerTime(event.date).user_time(self.timezone).done()
            
            row = [
                self._fmt_timestamp(timestamp),
                self._fmt(username),
                self._fmt(status_descriptions.get(event.status, "-")),
            ]
            
            result.append(row)
        
        return result
    
    def _fmt(self, val):
        if val is None:
            return format_datatables_data("-", "-")
        else:
            return format_datatables_data(val, val)
    
    def _fmt_timestamp(self, timestamp):
        return self.table_cell(
            timestamp,
            timestamp.strftime(SERVER_DATETIME_FORMAT),
        )
