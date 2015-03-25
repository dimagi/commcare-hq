from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from corehq.apps.reports.standard import DatespanMixin, ProjectReport,\
    ProjectReportParametersMixin
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader,\
    DTSortType
from corehq.apps.sms.filters import MessageTypeFilter
from corehq.util.timezones.conversions import ServerTime
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.web import get_url_base
from django.core.urlresolvers import reverse
from dimagi.utils.parsing import json_format_datetime
from corehq.apps.reports.util import format_datatables_data
from corehq.apps.users.models import CouchUser
from casexml.apps.case.models import CommCareCase
from django.conf import settings
from corehq.util.timezones import utils as tz_utils
import pytz
from corehq.apps.users.views import EditWebUserView
from corehq.apps.users.views.mobile.users import EditCommCareUserView
from corehq.apps.hqwebapp.doc_info import get_doc_info
from corehq.apps.sms.models import (
    WORKFLOW_REMINDER,
    WORKFLOW_KEYWORD,
    WORKFLOW_BROADCAST,
    WORKFLOW_CALLBACK,
    WORKFLOW_DEFAULT,
    INCOMING,
    OUTGOING,
    SMSLog,
)

class MessagesReport(ProjectReport, ProjectReportParametersMixin, GenericTabularReport, DatespanMixin):
    name = ugettext_noop('SMS Usage')
    slug = 'messages'
    fields = ['corehq.apps.reports.filters.select.GroupFilter',
              'corehq.apps.reports.filters.dates.DatespanFilter']

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
        from corehq.apps.users.views.mobile import EditCommCareUserView
        user_link = user_link_template % {
            "link": absolute_reverse(EditCommCareUserView.urlname,
                                     args=[self.domain, user._id]),
            "username": user.username_in_report
        }
        return self.table_cell(user.raw_username, user_link)

    @property
    def rows(self):
        def _row(user):
            # NOTE: this currently counts all messages from the user, whether
            # or not they were from verified numbers
            counts = _sms_count(user, self.datespan.startdate_utc, self.datespan.enddate_utc)
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
                group=self.group_id,
                user_ids=(self.individual,),
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

class BaseCommConnectLogReport(ProjectReport, ProjectReportParametersMixin, GenericTabularReport, DatespanMixin):
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

    def _fmt_contact_link(self, msg, doc_info):
        if doc_info:
            username, contact_type, url = (doc_info.display,
                doc_info.type_display, doc_info.link)
        else:
            username, contact_type, url = (None, None, None)
        username = username or "-"
        contact_type = contact_type or _("Unknown")
        if url:
            ret = self.table_cell(username, '<a href="%s">%s</a>' % (url, username))
        else:
            ret = self.table_cell(username, username)
        ret['raw'] = "|||".join([username, contact_type,
            msg.couch_recipient or ""])
        return ret

    def get_recipient_info(self, message, contact_cache):
        recipient_id = message.couch_recipient

        if recipient_id in contact_cache:
            return contact_cache[recipient_id]

        doc = None
        if recipient_id not in [None, ""]:
            try:
                if message.couch_recipient_doc_type == "CommCareCase":
                    doc = CommCareCase.get(recipient_id)
                else:
                    doc = CouchUser.get_by_user_id(recipient_id)
            except Exception:
                pass

        if doc:
            doc_info = get_doc_info(doc.to_json(), self.domain)
        else:
            doc_info = None

        contact_cache[recipient_id] = doc_info

        return doc_info

    @property
    def export_table(self):
        result = super(BaseCommConnectLogReport, self).export_table
        table = result[0][1]
        table[0].append(_("Contact Type"))
        table[0].append(_("Contact Id"))
        for row in table[1:]:
            contact_info = row[1].split("|||")
            row[1] = contact_info[0]
            row.append(contact_info[1])
            row.append(contact_info[2])
        return result

"""
Displays all sms for the given domain and date range.

Some projects only want the beginning digits in the phone number and not the entire phone number.
Since this isn't a common request, the decision was made to not have a field which lets you abbreviate
the phone number, but rather a settings parameter.

So, to have this report abbreviate the phone number to only the first four digits for a certain domain, add 
the domain to the list in settings.MESSAGE_LOG_OPTIONS["abbreviated_phone_number_domains"]
"""
class MessageLogReport(BaseCommConnectLogReport):
    name = ugettext_noop('Message Log')
    slug = 'message_log'
    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.sms.filters.MessageTypeFilter',
    ]
    exportable = True

    def get_message_type_filter(self):
        filtered_types = MessageTypeFilter.get_value(self.request, self.domain)
        if filtered_types:
            filtered_types = set([mt.lower() for mt in filtered_types])
            return lambda message_types: len(filtered_types.intersection(message_types)) > 0
        return lambda message_types: True

    @staticmethod
    def _get_message_types(message):
        relevant_workflows = [
            WORKFLOW_REMINDER,
            WORKFLOW_KEYWORD,
            WORKFLOW_BROADCAST,
            WORKFLOW_CALLBACK,
            WORKFLOW_DEFAULT,
        ]
        types = []
        if message.workflow in relevant_workflows:
            types.append(message.workflow.lower())
        if message.xforms_session_couch_id is not None:
            types.append(MessageTypeFilter.OPTION_SURVEY.lower())
        if not types:
            types.append(MessageTypeFilter.OPTION_OTHER.lower())
        return types

    @property
    def headers(self):
        header = DataTablesHeader(
            DataTablesColumn(_("Timestamp")),
            DataTablesColumn(_("User Name")),
            DataTablesColumn(_("Phone Number")),
            DataTablesColumn(_("Direction")),
            DataTablesColumn(_("Message")),
            DataTablesColumn(_("Type")),
        )
        header.custom_sort = [[0, 'desc']]
        return header

    @property
    def rows(self):
        startdate = json_format_datetime(self.datespan.startdate_utc)
        enddate = json_format_datetime(self.datespan.enddate_utc)
        data = SMSLog.by_domain_date(self.domain, startdate, enddate)
        result = []

        direction_map = {
            INCOMING: _("Incoming"),
            OUTGOING: _("Outgoing"),
        }

        # Retrieve message log options
        message_log_options = getattr(settings, "MESSAGE_LOG_OPTIONS", {})
        abbreviated_phone_number_domains = message_log_options.get("abbreviated_phone_number_domains", [])
        abbreviate_phone_number = (self.domain in abbreviated_phone_number_domains)

        contact_cache = {}
        message_type_filter = self.get_message_type_filter()

        for message in data:
            if message.direction == OUTGOING and not message.processed:
                continue

            message_types = self._get_message_types(message)
            if not message_type_filter(message_types):
                continue

            doc_info = self.get_recipient_info(message, contact_cache)

            phone_number = message.phone_number
            if abbreviate_phone_number and phone_number is not None:
                phone_number = phone_number[0:7] if phone_number[0:1] == "+" else phone_number[0:6]

            timestamp = ServerTime(message.date).user_time(self.timezone).done()
            result.append([
                self._fmt_timestamp(timestamp),
                self._fmt_contact_link(message, doc_info),
                self._fmt(phone_number),
                self._fmt(direction_map.get(message.direction,"-")),
                self._fmt(message.text),
                self._fmt(", ".join(message_types)),
            ])

        return result
