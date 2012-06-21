from corehq.apps.domain.models import Domain
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
    base_slug = 'data'
    template_name = "data_interfaces/data_interfaces_base.html"
    base_template_name = "data_interfaces/data_interfaces_base.html"
    asynchronous = True

class AppStoreInterface(DataInterface, StandardTabularHQReport, StandardDateHQReport):
    name = "App Store"
    slug = "appstore"
    fields = ['corehq.apps.reports.fields.SelectOrganizationField',
              'corehq.apps.reports.fields.SelectLicenseField',
              'corehq.apps.reports.fields.SelectCategoryField',
              'corehq.apps.reports.fields.SelectRegionField']

    template_name = 'data_interfaces/interfaces/case_management.html'

    def get_parameters(self):
        import pdb
        pdb.set_trace()
        all_groups = Group.get_reporting_groups(self.domain)
        self.all_case_sharing_groups = [group for group in all_groups if group.case_sharing]
        self.case_sharing_groups = []

        if self.group and self.group.case_sharing:
            self.case_sharing_groups = [self.group]
        elif not self.individual and not self.group:
            self.case_sharing_groups = self.all_case_sharing_groups

    def get_headers(self):
        headers = DataTablesHeader(
#            DataTablesColumn('Select  <a href="#" class="select-all btn btn-mini btn-inverse">all</a> <a href="#" class="select-none btn btn-mini btn-warning">none</a>', sortable=False, span=2),
            DataTablesColumn("Name", span=3),
            DataTablesColumn("Organization", span=2),
            DataTablesColumn("Category", span=2),
            DataTablesColumn("Copies", span=2),
            DataTablesColumn("License", span=2),
            DataTablesColumn("Last Modified", span=3, sort_type=DTSortType.NUMERIC)
        )
        headers.custom_sort = [[1, 'asc']]
        return headers

    def get_rows(self):
        rows = list()
#        checkbox = '<input type="checkbox" class="selected-commcare-case" data-bind="event: {change: updateCaseSelection}" data-caseid="%(case_id)s" data-owner="%(owner)s" data-ownertype="%(owner_type)s" />'
        data = self.get_data()
        for app in data:
#            app, app_link = self.get_app_info(item)
#            if app:
            rows.append(['<a href="%s">%s</a>' % (reverse('app_info', args=[app.name]), app.original_doc), app.organization, app.project_type, len(app.copies_of_parent()) , app.get_license_display, util.format_relative_date(app.snapshot_time)])
        return rows

    def get_data(self):
        return Domain.published_snapshots()[:40]

#        key = [self.domain, False, {}, owner_id ]
#        return get_db().view('case/by_date_modified_owner',
#                startkey=key+[self.datespan.startdate_param_utc],
#                endkey=key+[self.datespan.enddate_param_utc],
#                reduce=False,
#                include_docs=True
#            ).all()

    def get_app_info(self, data):
        app =  None
        app_link = ""
        if "doc" in data:
            app = CommCareCase.wrap(data["doc"])
        elif "id" in data:
            app = CommCareCase.get(data["id"])
        if app:
            app_link = '<a href="%s">%s</a>' %\
                        (reverse('app_info', args=[app.domain]), app.domain)
        return app, app_link

    def get_report_context(self):
        super(AppStoreInterface, self).get_report_context()
        active_users = util.get_all_users_by_domain(self.domain, filter_users=HQUserType.use_defaults())
        self.context['users'] = [dict(ownerid=user.userID, name=user.raw_username, type="user")
                                 for user in active_users]
        self.context['groups'] = [dict(ownerid=group.get_id, name=group.name, type="group")
                                  for group in self.all_case_sharing_groups]
