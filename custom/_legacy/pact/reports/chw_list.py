from django.urls import NoReverseMatch
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from django.utils.html import format_html
from corehq.apps.reports.util import make_form_couch_key
from corehq.util.dates import iso_string_to_datetime

from couchforms.models import XFormInstance


class PactCHWDashboard(GenericTabularReport, ProjectReportParametersMixin, CustomProjectReport):
    name = "CHW Management"
    slug = "chws"
    hide_filters = True
    fields = ['corehq.apps.reports.filters.users.UserTypeFilter', ]

    #    asynchronous = False
    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn("Username"),
            DataTablesColumn("Last Submit"),
            DataTablesColumn("Total Submits"),
        )
        return headers

    @property
    def rows(self):
        rows = []

        def form_count(user_id):
            key = make_form_couch_key(self.domain, user_id=user_id)
            result = XFormInstance.view('all_forms/view',
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
            v = XFormInstance.get_db().view('all_forms/view',
                endkey=key,
                startkey=key + [{}],
                reduce=False,
                include_docs=False,
                descending=True, limit=1
            )
            res = v.one()
            if res is None:
                return None
            else:
                return iso_string_to_datetime(res['key'][3]).strftime("%m/%d/%Y")

        for user in self.users:
            rows.append([
                user['raw_username'],
                last_submit_time(user['user_id']),
                form_count(user['user_id']),
            ])
        return rows
