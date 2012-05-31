from corehq.apps.reports.custom import HQReport
from django.core.urlresolvers import reverse
from casexml.apps.case.models import CommCareCase
from corehq.apps.reports import util
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.standard import StandardTabularHQReport, StandardDateHQReport
from corehq.apps.users.models import WebUser
from dimagi.utils.couch.database import get_db

class DataInterface(HQReport):

    def get_report_context(self):
        super(DataInterface, self).get_report_context()
        self.context['report_base'] = 'data_interfaces/data_interfaces_base.html'

class CaseReassignmentInterface(DataInterface, StandardTabularHQReport, StandardDateHQReport):
    name = "Reassign Cases"
    slug = "reassign_cases"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField',
              'corehq.apps.reports.fields.SelectMobileWorkerField',
              'corehq.apps.reports.fields.GroupField']
    template_name = 'data_interfaces/interfaces/case_management.html'

    def get_headers(self):
        headers = DataTablesHeader(
            DataTablesColumn('Select  <a href="#" class="select-all btn btn-mini btn-inverse">all</a> <a href="#" class="select-none btn btn-mini btn-warning">none</a>', sortable=False, span=2),
            DataTablesColumn("Case Name", span=3),
            DataTablesColumn("Case Type", span=2),
            DataTablesColumn("Owner", span=2),
            DataTablesColumn("Last Modified", span=3, sort_type=DTSortType.NUMERIC)
        )
        headers.custom_sort = [[1, 'asc']]
        return headers

    def get_rows(self):
        rows = list()
        for user in self.users:
            key = [self.domain, False, {}, user.userID ]
            data = get_db().view('case/by_date_modified_owner',
                startkey=key+[self.datespan.startdate_param_utc],
                endkey=key+[self.datespan.enddate_param_utc],
                reduce=False,
                include_docs=True
                ).all()
            for item in data:
                case =  None
                if "doc" in item:
                    case = CommCareCase.wrap(item["doc"])
                elif "id" in item:
                    case = CommCareCase.get(item["id"])
                if case:
                    fmt_case = '<a href="%s">%s</a>' % \
                               (reverse('case_details', args=[self.domain, case._id]), case.name)
                    rows.append(['<input type="checkbox" class="selected-commcare-case" data-bind="event: {change: updateCaseSelection}" data-caseid="%s" data-owner="%s" />' %\
                        (case._id, user.userID)
                        , fmt_case, case.type, user.username_in_report, util.format_relative_date(case.modified_on)])
        return rows

    def get_report_context(self):
        super(CaseReassignmentInterface, self).get_report_context()
        active_users = util.get_all_users_by_domain(self.domain, filter_users=HQUserType.use_defaults())
        self.context['available_owners'] = [dict(userid=user.userID, username=user.raw_username) for user in active_users]
