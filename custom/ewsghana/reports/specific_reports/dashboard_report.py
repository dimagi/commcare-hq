from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from custom.ewsghana.reports import MultiReport, ProductSelectionPane
from custom.ewsghana.reports.specific_reports.reporting_rates import ReportingRates, ReportingDetails
from custom.ewsghana.reports.specific_reports.stock_status_report import ProductAvailabilityData
from custom.ewsghana.reports.stock_levels_report import FacilityReportData, StockLevelsLegend, FacilitySMSUsers, \
    FacilityUsers, FacilityInChargeUsers, InventoryManagementData, InputStock


class DashboardReport(MultiReport):

    fields = [AsyncLocationFilter, DatespanFilter]
    name = "Dashboard report"
    title = "Dashboard report"
    slug = "dashboard_report"
    split = False

    @property
    def report_config(self):
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_utc,
            enddate=self.datespan.enddate_utc,
            location_id=self.request.GET.get('location_id'),
            program=None,
            products=None
        )

    @property
    def data_providers(self):
        config = self.report_config
        if self.is_reporting_type():
            self.split = True
            return [
                FacilityReportData(config),
                StockLevelsLegend(config),
                InputStock(config),
                FacilitySMSUsers(config),
                FacilityUsers(config),
                FacilityInChargeUsers(config),
                InventoryManagementData(config)
            ]
        self.split = False
        return [
            ProductSelectionPane(config=self.report_config),
            ProductAvailabilityData(config=self.report_config),
            ReportingRates(config=self.report_config),
            ReportingDetails(config=self.report_config)
        ]
