from datetime import datetime
from custom.ewsghana.filters import EWSLocationFilter
from custom.ewsghana.reports import MultiReport, ProductSelectionPane
from custom.ewsghana.reports.specific_reports.reporting_rates import ReportingRates, ReportingDetails
from custom.ewsghana.reports.specific_reports.stock_status_report import ProductAvailabilityData
from custom.ewsghana.reports.stock_levels_report import FacilityReportData, StockLevelsLegend, InputStock, \
    InventoryManagementData, UsersData
from custom.ewsghana.utils import get_country_id, calculate_last_period


class DashboardReport(MultiReport):

    fields = [EWSLocationFilter]
    name = "Dashboard"
    title = "Dashboard"
    slug = "dashboard_report"
    split = False

    @property
    def report_config(self):
        startdate, enddate = calculate_last_period(datetime.utcnow())
        return dict(
            domain=self.domain,
            startdate=startdate,
            enddate=enddate,
            location_id=self.request.GET.get('location_id') or get_country_id(self.domain),
            user=self.request.couch_user,
            program=None,
            products=None
        )

    @property
    def data_providers(self):
        config = self.report_config
        if self.is_reporting_type():
            self.split = True
            if self.is_rendered_as_email:
                return [FacilityReportData(config)]
            else:
                return [
                    FacilityReportData(config),
                    StockLevelsLegend(config),
                    InputStock(config),
                    UsersData(config),
                    InventoryManagementData(config),
                    ProductSelectionPane(config)
                ]
        self.split = False
        return [
            ProductAvailabilityData(config=self.report_config),
            ReportingRates(config=self.report_config),
            ReportingDetails(config=self.report_config)
        ]
