from corehq.apps.appstore.dispatcher import AppstoreDispatcher
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.reports.standard import DatespanMixin
from django.core.urlresolvers import reverse
from casexml.apps.case.models import CommCareCase
from corehq.apps.reports import util
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.generic import GenericReportView, GenericTabularReport
from corehq.apps.reports.models import HQUserType
from corehq.apps.users.models import WebUser
from dimagi.utils.couch.database import get_db

class AppstoreInterface(GenericReportView):
    section_name = "CommCare Exchange"
    app_slug = 'appstore'
    asynchronous = True
    exportable = False
    dispatcher = AppstoreDispatcher

    @property
    def default_report_url(self):
        return reverse('appstore_interfaces_default')


class CommCareExchangeAdvanced(GenericTabularReport, AppstoreInterface, DatespanMixin):
    name = "Exchange"
    slug = "advanced"
    fields = ['corehq.apps.reports.fields.SelectOrganizationField',
              'corehq.apps.reports.fields.SelectLicenseField',
              'corehq.apps.reports.fields.SelectCategoryField',
              'corehq.apps.reports.fields.SelectRegionField']

    report_template_path = 'data_interfaces/interfaces/case_management.html'

    _organization_filter = None
    @property
    def organization_filter(self):
        if self._organization_filter is None:
            self._organization_filter = self.request_params.get('org')
        return self._organization_filter

    _license_filter = None
    @property
    def license_filter(self):
        if self._license_filter is None:
            self._license_filter = self.request_params.get('license')
        return self._license_filter

    _category_filter = None
    @property
    def category_filter(self):
        if self._category_filter is None:
            self._category_filter = self.request_params.get('category')
        return self._category_filter

    _region_filter = None
    @property
    def region_filter(self):
        if self._region_filter is None:
            self._region_filter = self.request_params.get('region')
        return self._region_filter

    @property
    def headers(self):
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

    @property
    def rows(self):
        rows = list()
        data = self._get_data()
        for app in data:
            rows.append(['<a href="%s">%s</a>' % (reverse('project_info', args=[app.name]),
                                                  app.copied_from.display_name()),
                         app.organization_title(),
                         app.project_type,
                         len(app.copies_of_parent()),
                         app.get_license_display,
                         util.format_relative_date(app.snapshot_time)]
            )
        return rows

    def _get_data(self):
        query_parts = []
        if self.category_filter:
            query_parts.append('category:"%s"' % self.category_filter)
        elif self.license_filter:
            query_parts.append('license:"%s"' % self.license_filter)
        elif self.category_filter:
            query_parts.append('organization:"%s"' % self.organization_filter)
        elif self.region_filter:
            query_parts.append('region:"%s"' % self.region_filter)

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

