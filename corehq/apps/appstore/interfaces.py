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
    base_slug = 'appstore'
    template_name = "appstore/appstore_interfaces_base.html"
    base_template_name = "appstore/appstore_interfaces_base.html"
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
#        all_groups = Group.get_reporting_groups(self.domain)
#        self.all_case_sharing_groups = [group for group in all_groups if group.case_sharing]
#        self.case_sharing_groups = []
#
#        if self.group and self.group.case_sharing:
#            self.case_sharing_groups = [self.group]
#        elif not self.individual and not self.group:
#            self.case_sharing_groups = self.all_case_sharing_groups

        params = self.request_params
        self.organization_filter = None
        self.license_filter = None
        self.category_filter = None
        self.region_filter = None
        for filter in params:
            if filter == 'category':
                self.category_filter = params[filter]
            elif filter == 'license':
                self.license_filter = params[filter]
            elif filter == 'org':
                self.organization_filter = params[filter]
            elif filter == 'region':
                self.region_filter = params[filter]


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
            rows.append(['<a href="%s">%s</a>' % (reverse('app_info', args=[app.name]), app.original_doc), app.organization, app.project_type, len(app.copies_of_parent()) , app.get_license_display, util.format_relative_date(app.snapshot_time)])
        return rows

    def get_data(self):
        return Domain.published_snapshots()[:40]

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
                        (reverse('app_info', args=[app.domain]), app.domain)
        return app, app_link

