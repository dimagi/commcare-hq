from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from casexml.apps.case.models import CommCareCase
from corehq.apps.sms.models import ExpectedCallbackEventLog, CALLBACK_PENDING, CALLBACK_RECEIVED, CALLBACK_MISSED
from datetime import datetime, timedelta
from dimagi.utils.timezones import utils as tz_utils
import pytz

class MissedCallbackReport(CustomProjectReport, GenericTabularReport):
    name = ugettext_noop("Missed Callbacks")
    slug = "missed_callbacks"
    description = ugettext_noop("Summarizes two weeks of SMS and Callback interactions for all participants.")
    hide_filters = True
    flush_layout = True
    
    def get_past_two_weeks(self):
        if self.request.couch_user.is_commcare_user():
            time_zone = self.request.couch_user.get_time_zone()
        else:
            time_zone = None
        
        now = datetime.utcnow()
        if time_zone is None:
            local_datetime = now
        else:
            local_datetime = tz_utils.adjust_datetime_to_timezone(now, pytz.utc.zone, pytz.timezone(time_zone).zone)
        
        return [(local_datetime + timedelta(days = x)).strftime("%Y-%m-%d") for x in range(-14, 0)]
    
    @property
    def headers(self):
        args = [
            DataTablesColumn(_("Participant ID")),
            DataTablesColumn(_("Total No Response")),
            DataTablesColumn(_("Total Indicated")),
            DataTablesColumn(_("Total Pending")),
        ]
        args += [DataTablesColumn(date) for date in self.get_past_two_weeks()]
        return DataTablesHeader(*args)
    
    @property
    def rows(self):
        return []

