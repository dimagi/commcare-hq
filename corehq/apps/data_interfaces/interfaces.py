from corehq.apps.groups.models import Group
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
              'corehq.apps.reports.fields.CaseSharingGroupField']
    template_name = 'data_interfaces/interfaces/case_management.html'

    def get_parameters(self):
        all_groups = Group.get_reporting_groups(self.domain)
        self.all_case_sharing_groups = [group for group in all_groups if group.case_sharing]
        self.case_sharing_groups = []
        
        if self.group and self.group.case_sharing:
            self.case_sharing_groups = [self.group]
        elif not self.individual and not self.group:
            self.case_sharing_groups = self.all_case_sharing_groups

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
        checkbox = '<input type="checkbox" class="selected-commcare-case" data-bind="event: {change: updateCaseSelection}" data-caseid="%(case_id)s" data-owner="%(owner)s" data-ownertype="%(owner_type)s" />'
        for user in self.users:
            data = self.get_data(user.userID)
            for item in data:
                case, case_link = self.get_case_info(item)
                if case:
                    rows.append([checkbox % dict(case_id=case._id, owner=user.userID, owner_type="user"),
                                 case_link, case.type, user.username_in_report, util.format_relative_date(case.modified_on)])
        for group in self.case_sharing_groups:
            data = self.get_data(group.get_id)
            for item in data:
                case, case_link = self.get_case_info(item)
                if case:
                    rows.append([checkbox % dict(case_id=case._id, owner=group.get_id, owner_type="group"),
                                 case_link, case.type, '%s <span class="label label-inverse" title="%s">group</span>' % (group.name, group.name),
                                 util.format_relative_date(case.modified_on)])
        return rows

    def get_data(self, owner_id):
        key = [self.domain, False, {}, owner_id ]
        return get_db().view('case/by_date_modified_owner',
                startkey=key+[self.datespan.startdate_param_utc],
                endkey=key+[self.datespan.enddate_param_utc],
                reduce=False,
                include_docs=True
            ).all()

    def get_case_info(self, data):
        case =  None
        case_link = ""
        if "doc" in data:
            case = CommCareCase.wrap(data["doc"])
        elif "id" in data:
            case = CommCareCase.get(data["id"])
        if case:
            case_link = '<a href="%s">%s</a>' %\
                        (reverse('case_details', args=[self.domain, case._id]), case.name)
        return case, case_link

    def get_report_context(self):
        super(CaseReassignmentInterface, self).get_report_context()
        active_users = util.get_all_users_by_domain(self.domain, filter_users=HQUserType.use_defaults())
        self.context['users'] = [dict(ownerid=user.userID, name=user.raw_username, type="user")
                                 for user in active_users]
        self.context['groups'] = [dict(ownerid=group.get_id, name=group.name, type="group")
                                  for group in self.all_case_sharing_groups]
