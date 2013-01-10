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
                group=self.group_id,
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
