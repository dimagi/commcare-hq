from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from corehq.apps.reports.standard import DatespanMixin, ProjectReport,\
    ProjectReportParametersMixin
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from dimagi.utils.parsing import json_format_datetime
from corehq.apps.sms.models import INCOMING, OUTGOING, CallLog, ExpectedCallbackEventLog, CALLBACK_PENDING, CALLBACK_RECEIVED, CALLBACK_MISSED
from corehq.apps.smsforms.models import XFormsSession
from corehq.apps.reports.util import format_datatables_data
from corehq.apps.users.models import CouchUser
from casexml.apps.case.models import CommCareCase
from django.conf import settings
from dimagi.utils.timezones import utils as tz_utils
from corehq.apps.reminders.util import get_form_name
import pytz

class CallLogReport(ProjectReport, ProjectReportParametersMixin, GenericTabularReport, DatespanMixin):
    """
    Displays all calls for the given domain and date range.
    """
    name = ugettext_noop('Call Log')
    slug = 'call_log'
    fields = ['corehq.apps.reports.filters.dates.DatespanFilter']
    exportable = True
    emailable = True
    
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
        
        return DataTablesHeader(*header_list)
    
    @property
    def rows(self):
        startdate = json_format_datetime(self.datespan.startdate_utc)
        enddate = json_format_datetime(self.datespan.enddate_utc)
        data = CallLog.by_domain_date(self.domain, startdate, enddate)
        result = []
        
        # Store the results of lookups for faster loading
        username_map = {} 
        form_map = {}
        
        direction_map = {
            INCOMING: _("Incoming"),
            OUTGOING: _("Outgoing"),
        }
        
        # Retrieve message log options
        message_log_options = getattr(settings, "MESSAGE_LOG_OPTIONS", {})
        abbreviated_phone_number_domains = message_log_options.get("abbreviated_phone_number_domains", [])
        abbreviate_phone_number = (self.domain in abbreviated_phone_number_domains)
        
        for call in data:
            recipient_id = call.couch_recipient
            if recipient_id in [None, ""]:
                username = "-"
            elif recipient_id in username_map:
                username = username_map.get(recipient_id)
            else:
                username = "-"
                try:
                    if call.couch_recipient_doc_type == "CommCareCase":
                        username = CommCareCase.get(recipient_id).name
                    else:
                        username = CouchUser.get_by_user_id(recipient_id).username
                except Exception:
                    pass
               
                username_map[recipient_id] = username
            
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
            
            timestamp = tz_utils.adjust_datetime_to_timezone(call.date, pytz.utc.zone, self.timezone.zone)
            
            if call.direction == INCOMING:
                answered = "-"
            else:
                answered = _("Yes") if call.answered else _("No")
            
            if call.xforms_session_id is None:
                submission_id = None
            else:
                session = XFormsSession.latest_by_session_id(call.xforms_session_id)
                submission_id = session.submission_id
            
            row = [
                self._fmt_timestamp(timestamp),
                self._fmt(username),
                self._fmt(phone_number),
                self._fmt(direction_map.get(call.direction,"-")),
                self._fmt(form_name),
                self._fmt("-") if submission_id is None else self._fmt_submission_link(submission_id),
                self._fmt(answered),
                self._fmt(call.duration),
                self._fmt(_("Yes") if call.error else _("No")),
                self._fmt(call.error_message),
            ]
            
            if self.request.couch_user.is_previewer():
                row.append(self._fmt(call.gateway_session_id))
            
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
            timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        )
    
    def _fmt_submission_link(self, submission_id):
        url = reverse("render_form_data", args=[self.domain, submission_id])
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
        startdate = json_format_datetime(self.datespan.startdate_utc)
        enddate = json_format_datetime(self.datespan.enddate_utc)
        data = ExpectedCallbackEventLog.by_domain(self.domain, startdate, enddate)
        result = []
        
        status_descriptions = {
            CALLBACK_PENDING : _("Pending"),
            CALLBACK_RECEIVED : _("Received"),
            CALLBACK_MISSED : _("Missed"),
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
            
            timestamp = tz_utils.adjust_datetime_to_timezone(event.date, pytz.utc.zone, self.timezone.zone)
            
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
            timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        )

