import random
from django.core.urlresolvers import reverse, NoReverseMatch
from corehq.apps.hqcase.paginator import CasePaginator
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.fields import SelectMobileWorkerField
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from corehq.apps.reports.standard.inspect import CaseListReport, CaseDisplay, CaseListMixin
from django.utils import html

from couchdbkit.resource import RequestFailed
from corehq.apps.users.models import CouchUser, CommCareUser
from couchforms.models import XFormInstance
from dimagi.utils.decorators.memoized import memoized
from pact.reports import PatientNavigationReport
from pact.reports.chw import PactCHWProfileReport
from pact.reports.patient import PactPatientInfoReport


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
            DataTablesColumn("Actions"),
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
            result = XFormInstance.view('couchforms/by_user',
                                        startkey=[user_id],
                                        endkey=[user_id, {}],
                                        group_level=0
            ).one()
            if result:
                return result['value']
            else:
                return 0


        def last_submit_time(user_id):
            #need to call it directly due to reversed not liking the keys set the regular way
            v = XFormInstance.view('couchforms/by_user',
                                   endkey=[user_id],
                                   startkey=[user_id, {}],
                                   reduce=False,
                                   include_docs=True,
                                   descending=True, limit=1)
#            print v.params
            res = v.one()
            if res is None:
                return None
            else:
                return res.received_on.strftime("%m/%d/%Y")


        for user in self.users:
            rows.append([
                user['raw_username'],
                last_submit_time(user['user_id']),
                form_count(user['user_id']),
                self._chw_profile_link(user['user_id'])
            ])
        return rows

