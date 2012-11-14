from django.utils.safestring import mark_safe
from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher
from corehq.apps.groups.models import Group
from django.core.urlresolvers import reverse
from corehq.apps.reports import util
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.generic import GenericReportView
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.standard.inspect import CaseListMixin
from dimagi.utils.decorators.memoized import memoized

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

class CaseReassignmentInterface(CaseListMixin, DataInterface):
    name = "Reassign Cases"
    slug = "reassign_cases"

    report_template_path = 'data_interfaces/interfaces/case_management.html'

    asynchronous = False
    ajax_pagination = True

    @property
    @memoized
    def all_case_sharing_groups(self):
        return Group.get_case_sharing_groups(self.domain)

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(mark_safe('Select  <a href="#" class="select-all btn btn-mini btn-inverse">all</a> <a href="#" class="select-none btn btn-mini btn-warning">none</a>'), sortable=False, span=2),
            DataTablesColumn("Case Name", span=3),
            DataTablesColumn("Case Type", span=2),
            DataTablesColumn("Owner", span=2),
            DataTablesColumn("Last Modified", span=3, sort_type=DTSortType.NUMERIC)
        )
#        headers.custom_sort = [[1, 'asc']]
        headers.no_sort = True
        return headers

    @property
    def rows(self):
        checkbox = mark_safe('<input type="checkbox" class="selected-commcare-case" data-bind="event: {change: updateCaseSelection}" data-caseid="%(case_id)s" data-owner="%(owner)s" data-ownertype="%(owner_type)s" />')
        for row in self.case_results['rows']:
            case = self.get_case(row)
            display = self.CaseDisplay(case)
            yield [
                checkbox % dict(case_id=case._id, owner=display.owner_id, owner_type=display.owner_type),
                display.case_link,
                display.case_type,
                display.owner_display,
                util.format_relative_date(case.modified_on)['html'],
            ]

    @property
    def report_context(self):
        context = super(CaseReassignmentInterface, self).report_context
        active_users = util.get_all_users_by_domain(self.domain, user_filter=HQUserType.use_defaults(), simplified=True)
        context.update(
            users=[dict(ownerid=user.get('user_id'), name=user.get('username_in_report'), type="user")
                   for user in active_users],
            groups=[dict(ownerid=group.get_id, name=group.name, type="group")
                    for group in self.all_case_sharing_groups],
            user_ids=self.user_ids,
        )
        return context
