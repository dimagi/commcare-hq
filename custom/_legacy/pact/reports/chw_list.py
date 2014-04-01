from django.core.urlresolvers import  NoReverseMatch
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from django.utils import html
from corehq.apps.reports.util import make_form_couch_key

from couchforms.models import XFormInstance
from pact.reports.chw import PactCHWProfileReport
from datetime import datetime


class PactCHWDashboard(GenericTabularReport, ProjectReportParametersMixin, CustomProjectReport):
    name = "CHW Management"
    slug = "chws"
    hide_filters = True
    fields = ['corehq.apps.reports.fields.FilterUsersField', ]

    #    asynchronous = False
    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn("Username"),
            DataTablesColumn("Last Submit"),
            DataTablesColumn("Total Submits"),
            DataTablesColumn("", sortable=False),
        )
        return headers

    def _chw_profile_link(self, user_id):
        try:
            return html.mark_safe("<a class='ajax_dialog' href='%s'>%s</a>" % (
                html.escape(PactCHWProfileReport.get_url(*[self.domain]) + "?chw_id=%s" % user_id),
                "View Profile",
                ))
        except NoReverseMatch:
            return "Unknown User ID"

    @property
    def rows(self):
        rows = []
        def form_count(user_id):
            key = make_form_couch_key(self.domain, user_id=user_id)
            result = XFormInstance.view('reports_forms/all_forms',
                                        startkey=key,
                                        endkey=key + [{}],
                                        group_level=0
            ).one()
            if result:
                return result['value']
            else:
                return 0


        def last_submit_time(user_id):
            #need to call it directly due to reversed not liking the keys set the regular way
            key = make_form_couch_key(self.domain, user_id=user_id)
            v = XFormInstance.view('reports_forms/all_forms',
                                   endkey=key,
                                   startkey=key + [{}],
                                   reduce=False,
                                   include_docs=False,
                                   descending=True, limit=1)
            res = v.one()
            if res is None:
                return None
            else:
                return datetime.strftime(res['key'][3], "%Y-%m-%dT%H:%M:%SZ").strftime("%m/%d/%Y")


        for user in self.users:
            rows.append([
                user['raw_username'],
                last_submit_time(user['user_id']),
                form_count(user['user_id']),
                self._chw_profile_link(user['user_id'])
            ])
        return rows

