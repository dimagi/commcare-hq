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
    base_slug = 'advanced'
    template_name = "appstore/appstore_interfaces_base.html"
    base_template_name = "appstore/appstore_interfaces_base.html"
    asynchronous = True
    exportable = False

class AppStoreInterface(DataInterface, StandardTabularHQReport, StandardDateHQReport):
    name = "Exchange"
    slug = "advanced"
    fields = ['corehq.apps.reports.fields.SelectOrganizationField',
              'corehq.apps.reports.fields.SelectLicenseField',
              'corehq.apps.reports.fields.SelectCategoryField',
              'corehq.apps.reports.fields.SelectRegionField']

    template_name = 'data_interfaces/interfaces/case_management.html'

    def get_parameters(self):
#        all_groups = Group.get_reporting_groups(self.domain)
#        self.all_case_sharing_groups = [group for group in all_groups if group.case_sharing]
#        self.case_sharing_groups = []
#
#        if self.group and self.group.case_sharing:
#            self.case_sharing_groups = [self.group]
#        elif not self.individual and not self.group:
#            self.case_sharing_groups = self.all_case_sharing_groups

        params = self.request_params
        self.organization_filter = params.get('org')
        self.license_filter = params.get('license')
        self.category_filter = params.get('category')
        self.region_filter = params.get('region')
#        self.search_filter = params.get('sSearch')


    def get_headers(self):
        headers = DataTablesHeader(
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
        data = self.get_data()
        for app in data:
            rows.append(['<a href="%s">%s</a>' % (reverse('project_info', args=[app.name]), app.copied_from().display_name()), app.organization_title(), app.project_type, len(app.copies_of_parent()) , app.get_license_display, util.format_relative_date(app.snapshot_time)])
        return rows

    def get_data(self):
        query_parts = []
        if self.category_filter:
            query_parts.append('category:"%s"' % (self.category_filter))
        elif self.license_filter:
            query_parts.append('license:"%s"' % (self.license_filter))
        elif self.category_filter:
            query_parts.append('organization:"%s"' % (self.organization_filter))
        elif self.region_filter:
            query_parts.append('region:"%s"' % (self.region_filter))

        if len(query_parts) > 0:
            query = ' '.join(query_parts)
            snapshots = Domain.snapshot_search(query)
        else:
            snapshots = Domain.published_snapshots()[:20]
        return snapshots

         # use self.organization_filter, self.license_filter, self.category_filter and self.region_filter to search with lucene


    def get_app_info(self, data):
        app =  None
        app_link = ""
        if "doc" in data:
            app = CommCareCase.wrap(data["doc"])
        elif "id" in data:
            app = CommCareCase.get(data["id"])
        if app:
            app_link = '<a href="%s">%s</a>' %\
                        (reverse('project_info', args=[app.domain]), app.domain)
        return app, app_link

