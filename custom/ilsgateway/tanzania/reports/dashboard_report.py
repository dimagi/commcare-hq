from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.hqwebapp.decorators import (
    use_daterangepicker,
    use_datatables,
    use_jquery_ui,
    use_nvd3,
)
from custom.ilsgateway.filters import (
    ProgramFilter,
    B3ILSDateFilter,
    B3ILSAsyncLocationFilter,
)
from custom.ilsgateway.tanzania import MultiReport
from custom.ilsgateway.tanzania.reports.configs.dashboard_config import DashboardConfig
from custom.ilsgateway.tanzania.reports.facility_details import InventoryHistoryData, RegistrationData, \
    RandRHistory, Notes, RecentMessages
from custom.ilsgateway.tanzania.reports.mixins import RandRSubmissionData, DistrictSummaryData, \
    SohSubmissionData, DeliverySubmissionData, ProductAvailabilitySummary
from custom.ilsgateway.tanzania.reports.stock_on_hand import StockOnHandReport
from custom.ilsgateway.tanzania.reports.utils import make_url
from memoized import memoized
from django.utils.translation import ugettext as _


class DashboardReport(MultiReport):
    slug = 'ils_dashboard_report'
    name = "Dashboard report"

    @use_datatables
    @use_daterangepicker
    @use_jquery_ui
    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        pass

    @property
    def fields(self):
        fields = [B3ILSAsyncLocationFilter, B3ILSDateFilter, ProgramFilter]
        if self.location and self.location.location_type.name.upper() == 'FACILITY':
            fields = []
        return fields

    @property
    def title(self):
        title = _("Dashboard report {0}".format(self.title_month))
        if self.location and self.location.location_type.name.upper() == 'FACILITY':
            return "{0} ({1}) Group {2}".format(self.location.name,
                                                self.location.site_code,
                                                self.location.metadata.get('group', '---'))
        return title

    @property
    def report_context(self):
        report_context = super(DashboardReport, self).report_context
        report_context.update({'with_supervision_url': True})
        return report_context

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        if self.location:
            if self.location.location_type.name.upper() == 'FACILITY':
                self.use_datatables = True
                return [
                    InventoryHistoryData(config=config),
                    RandRHistory(config=config),
                    Notes(config=config),
                    RecentMessages(config=config),
                    RegistrationData(config=dict(loc_type='FACILITY', **config), css_class='row_chart_all'),
                    RegistrationData(config=dict(loc_type='DISTRICT', **config), css_class='row_chart_all'),
                    RegistrationData(config=dict(loc_type='REGION', **config), css_class='row_chart_all')
                ]
            else:
                self.use_datatables = False
                return [
                    RandRSubmissionData(config=config),
                    DistrictSummaryData(config=config),
                    SohSubmissionData(config=config),
                    DeliverySubmissionData(config=config),
                    ProductAvailabilitySummary(config=config, css_class='row_chart_all')
                ]
        else:
            return []

    @property
    def report_facilities_url(self):
        config = self.report_config
        return make_url(
            StockOnHandReport,
            self.domain,
            '?location_id=%s&filter_by_program=%s&datespan_type=%s&datespan_first=%s&datespan_second=%s',
            (config['location_id'], config['program'], self.type, self.first, self.second)
        )
