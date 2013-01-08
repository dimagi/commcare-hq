from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from corehq.apps.reports.standard import DatespanMixin, ProjectReport,\
    ProjectReportParametersMixin
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader,\
    DTSortType
from dimagi.utils.web import get_url_base
from django.core.urlresolvers import reverse
from dimagi.utils.parsing import json_format_datetime
from corehq.apps.sms.models import INCOMING, OUTGOING, SMSLog
from datetime import timedelta
from corehq.apps.reports.util import format_datatables_data
from corehq.apps.users.models import CouchUser
from casexml.apps.case.models import CommCareCase
from django.conf import settings

class MessagesReport(ProjectReport, ProjectReportParametersMixin, GenericTabularReport, DatespanMixin):
    name = ugettext_noop('SMS Usage')
    slug = 'messages'
    fields = ['corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']

    special_notice = ugettext_noop(
        "This report will only show data for users whose phone numbers have "
        "been verified. Phone numbers can be verified from the Settings and "
        "Users tab.")

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("User Name")),
            DataTablesColumn(_("Number of Messages Received"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Number of Messages Sent"), sort_type=DTSortType.NUMERIC),
            # DataTablesColumn(_("Number of Error Messages Sent"), sort_type=DTSortType.NUMERIC), # TODO
            DataTablesColumn(_("Number of Phone Numbers Used"), sort_type=DTSortType.NUMERIC),
        )

    def get_user_link(self, user):
        user_link_template = '<a href="%(link)s">%(username)s</a>'
        user_link = user_link_template % {"link": "%s%s" % (get_url_base(),
                                                            reverse('user_account', args=[self.domain, user._id])),
                                          "username": user.username_in_report}
        return self.table_cell(user.raw_username, user_link)

    @property
    def rows(self):
        def _row(user):
            # NOTE: this currently counts all messages from the user, whether
            # or not they were from verified numbers
            # HACK: in order to make the endate inclusive we have to set it
            # to tomorrow
            enddate = self.datespan.enddate + timedelta(days=1)
            counts = _sms_count(user, self.datespan.startdate, enddate)
            def _fmt(val):
                return format_datatables_data(val, val)
            return [
                self.get_user_link(user),
                _fmt(counts[OUTGOING]),
                _fmt(counts[INCOMING]),
                _fmt(len(user.get_verified_numbers()))
            ]

        return [
            _row(user) for user in self.get_all_users_by_domain(
                group=self.group_name,
                individual=self.individual,
                user_filter=tuple(self.user_filter),
                simplified=False
            )
        ]

def _sms_count(user, startdate, enddate, message_type='SMSLog'):
    """
    Returns a dictionary of messages seen for a given type, user, and date
    range of the format:
    {
        I: inbound_count,
        O: outbound_count
    }
    """
    # utilizable if we want to stick it somewhere else
    start_timestamp = json_format_datetime(startdate)
    end_timestamp = json_format_datetime(enddate)
    ret = {}
    for direction in [INCOMING, OUTGOING]:
        results = SMSLog.get_db().view("sms/by_recipient",
            startkey=[user.doc_type, user._id, message_type, direction, start_timestamp],
            endkey=[user.doc_type, user._id, message_type, direction, end_timestamp],
            reduce=True).all()
        ret[direction] = results[0]['value'] if results else 0

    return ret

"""
Displays all sms for the given domain and date range.

Some projects only want the beginning digits in the phone number and not the entire phone number.
Since this isn't a common request, the decision was made to not have a field which lets you abbreviate
the phone number, but rather a settings parameter.

So, to have this report abbreviate the phone number to only the first four digits for a certain domain, add 
the domain to the list in settings.MESSAGE_LOG_OPTIONS["abbreviated_phone_number_domains"]
"""
class MessageLogReport(ProjectReport, ProjectReportParametersMixin, GenericTabularReport, DatespanMixin):
    name = ugettext_noop('Message Log')
    slug = 'message_log'
    fields = ['corehq.apps.reports.fields.DatespanField']
    exportable = True
    
    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Timestamp")),
            DataTablesColumn(_("User Name")),
            DataTablesColumn(_("Phone Number")),
            DataTablesColumn(_("Direction")),
            DataTablesColumn(_("Message")),
        )
    
    @property
    def rows(self):
        startdate = json_format_datetime(self.datespan.startdate)
        enddate = self.datespan.enddate + timedelta(days=1) # Make end date inclusive
        enddate = json_format_datetime(enddate)
        data = SMSLog.by_domain_date(self.domain, startdate, enddate)
        result = []
        
        username_map = {} # Store the results of username lookups for faster loading
        
        direction_map = {
            INCOMING: _("Incoming"),
            OUTGOING: _("Outgoing"),
        }
        
        # Retrieve message log options
        message_log_options = getattr(settings, "MESSAGE_LOG_OPTIONS", {})
        abbreviated_phone_number_domains = message_log_options.get("abbreviated_phone_number_domains", [])
        abbreviate_phone_number = (self.domain in abbreviated_phone_number_domains)
        
        for message in data:
            recipient_id = message.couch_recipient
            if recipient_id is None:
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
            
            phone_number = message.phone_number
            if abbreviate_phone_number and phone_number is not None:
                phone_number = phone_number[0:5]
            
            result.append([
                self._fmt_timestamp(message.date),
                self._fmt(username),
                self._fmt(phone_number),
                self._fmt(direction_map.get(message.direction,"-")),
                self._fmt(message.text),
            ])
        
        return result
    
    def _fmt(self, val):
        return format_datatables_data(val, val)
    
    def _fmt_timestamp(self, timestamp):
        return self.table_cell(
            timestamp,
            timestamp.strftime("%d %b %Y, %H:%M:%S"),
        )

