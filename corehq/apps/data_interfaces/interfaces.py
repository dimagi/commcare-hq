from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher
from corehq.apps.groups.models import Group
from corehq.apps.reports.standard import DatespanMixin, ProjectReportParametersMixin
from django.core.urlresolvers import reverse
from casexml.apps.case.models import CommCareCase
from corehq.apps.reports import util
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.generic import GenericReportView, GenericTabularReport
from corehq.apps.reports.models import HQUserType
from corehq.apps.users.models import WebUser
from dimagi.utils.couch.database import get_db

class DataInterface(GenericReportView):
    # overriding properties from GenericReportView
    section_name = 'Manage Data'
    app_slug = 'data_interfaces'
    asynchronous = True
    dispatcher = DataInterfaceDispatcher
    exportable = False

    @property
    def default_report_url(self):
        return reverse('data_interfaces_default', args=[self.request.project])

class CaseReassignmentInterface(GenericTabularReport, DataInterface, ProjectReportParametersMixin, DatespanMixin):
    name = "Reassign Cases"
    slug = "reassign_cases"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField',
              'corehq.apps.reports.fields.SelectCaseOwnerField',
              'corehq.apps.reports.fields.SelectReportingGroupField']
    report_template_path = 'data_interfaces/interfaces/case_management.html'

    _all_case_sharing_groups = None
    @property
    def all_case_sharing_groups(self):
        if self._all_case_sharing_groups is None:
            self._all_case_sharing_groups = Group.get_case_sharing_groups(self.domain)
        return self._all_case_sharing_groups

    _case_sharing_groups = None
    @property
    def case_sharing_groups(self):
        if self._case_sharing_groups is None:
            self._case_sharing_groups = self.all_case_sharing_groups
            if self.individual:
                try:
                    group = Group.get(self.individual)
                except Exception:
                    group = None
                if group:
                    self._users = []
                    self._case_sharing_groups = [group]
        return self._case_sharing_groups

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn('Select  <a href="#" class="select-all btn btn-mini btn-inverse">all</a> <a href="#" class="select-none btn btn-mini btn-warning">none</a>', sortable=False, span=2),
            DataTablesColumn("Case Name", span=3),
            DataTablesColumn("Case Type", span=2),
            DataTablesColumn("Owner", span=2),
            DataTablesColumn("Last Modified", span=3, sort_type=DTSortType.NUMERIC)
        )
        headers.custom_sort = [[1, 'asc']]
        return headers

    @property
    def rows(self):
        rows = list()
        checkbox = '<input type="checkbox" class="selected-commcare-case" data-bind="event: {change: updateCaseSelection}" data-caseid="%(case_id)s" data-owner="%(owner)s" data-ownertype="%(owner_type)s" />'
        for user in self.users:
            data = self._get_data(user.get('user_id'))
            for item in data:
                case, case_link = self._get_case_info(item)
                if case:
                    rows.append([checkbox % dict(case_id=case._id, owner=user.get('user_id'), owner_type="user"),
                                 case_link, case.type, user.get('username_in_report'), util.format_relative_date(case.modified_on)])
        for group in self.case_sharing_groups:
            data = self._get_data(group._id)
            for item in data:
                case, case_link = self._get_case_info(item)
                if case:
                    rows.append([checkbox % dict(case_id=case._id, owner=group.get_id, owner_type="group"),
                                 case_link, case.type, '%s <span class="label label-inverse" title="%s">group</span>' % (group.name, group.name),
                                 util.format_relative_date(case.modified_on)])
        return rows

    def _get_data(self, owner_id):
        key = [self.domain, "open", {}, owner_id ]
        return get_db().view('case/by_date_modified_owner',
                startkey=key+[self.datespan.startdate_param_utc],
                endkey=key+[self.datespan.enddate_param_utc],
                reduce=False,
                include_docs=True
            ).all()

    def _get_case_info(self, data):
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

    @property
    def report_context(self):
        context = super(CaseReassignmentInterface, self).report_context
        active_users = util.get_all_users_by_domain(self.domain, user_filter=HQUserType.use_defaults(), simplified=True)
        context.update(
            users=[dict(ownerid=user.get('user_id'), name=user.get('username_in_report'), type="user")
                   for user in active_users],
            groups=[dict(ownerid=group.get_id, name=group.name, type="group")
                    for group in self.all_case_sharing_groups]
        )
        return context
