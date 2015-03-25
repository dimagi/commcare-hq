from custom.ilsgateway.filters import ProductByProgramFilter
from custom.ilsgateway.tanzania import MultiReport
from custom.ilsgateway.tanzania.reports.facility_details import InventoryHistoryData, RegistrationData, \
    RandRHistory
from custom.ilsgateway.tanzania.reports.mixins import RandRSubmissionData, DistrictSummaryData, \
    SohSubmissionData, DeliverySubmissionData, ProductAvailabilitySummary
from custom.ilsgateway.tanzania.reports.stock_on_hand import StockOnHandReport
from custom.ilsgateway.tanzania.reports.utils import make_url
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import YearFilter, MonthFilter
from dimagi.utils.decorators.memoized import memoized
from django.utils import html
from django.utils.translation import ugettext as _


class DashboardReport(MultiReport):
    slug = 'ils_dashboard_report'
    name = "Dashboard report"

    @property
    def title(self):
        title = _("Dashboard report")
        if self.location and self.location.location_type.name.upper() == 'FACILITY':
            title = _('Facility Details')
        return title

    @property
    def fields(self):
        fields = [AsyncLocationFilter, MonthFilter, YearFilter, ProductByProgramFilter]
        if self.location and self.location.location_type.name.upper() == 'FACILITY':
            fields = [AsyncLocationFilter, ProductByProgramFilter]
        return fields

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
        return html.escape(make_url(
            StockOnHandReport,
            self.domain,
            '?location_id=%s&month=%s&year=%s&filter_by_program=%s%s',
            (config['location_id'], config['month'], config['year'], config['program'], config['prd_part_url'])
        ))
