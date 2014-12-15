from custom.ilsgateway.filters import ProductByProgramFilter
from custom.ilsgateway.tanzania import MultiReport
from custom.ilsgateway.tanzania.reports.mixins import RandRSubmissionData, DistrictSummaryData, \
    SohSubmissionData, DeliverySubmissionData, ProductAvailabilitySummary
from custom.ilsgateway.tanzania.reports.stock_on_hand import StockOnHandReport
from custom.ilsgateway.tanzania.reports.utils import make_url
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import YearFilter, MonthFilter
from dimagi.utils.decorators.memoized import memoized
from django.utils import html


class DashboardReport(MultiReport):
    title = "Dashboard report"
    fields = [AsyncLocationFilter, MonthFilter, YearFilter, ProductByProgramFilter]
    name = "Dashboard report"
    slug = 'ils_dashboard_report'

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [RandRSubmissionData(config=config),
                DistrictSummaryData(config=config),
                SohSubmissionData(config=config),
                DeliverySubmissionData(config=config),
                ProductAvailabilitySummary(config=config, css_class='row_chart_all')]

    @property
    def report_facilities_url(self):
        config = self.report_config
        return html.escape(make_url(
            StockOnHandReport,
            self.domain,
            '?location_id=%s&month=%s&year=%s&filter_by_program=%s%s',
            (config['location_id'], config['month'], config['year'], config['program'], config['prd_part_url'])
        ))
