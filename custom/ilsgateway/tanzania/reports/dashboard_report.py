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
    fields = [AsyncLocationFilter, MonthFilter, YearFilter]
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
        return html.escape(make_url(
            StockOnHandReport,
            self.domain,
            '?location_id=%s&month=%s&year=%s',
            (self.request_params['location_id'], self.request_params['month'], self.request_params['year'])
        ))
