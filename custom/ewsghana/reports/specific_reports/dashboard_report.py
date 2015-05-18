from corehq.apps.reports.filters.dates import DatespanFilter
from custom.ewsghana.filters import EWSLocationFilter
from custom.ewsghana.reports import MultiReport, ProductSelectionPane
from custom.ewsghana.reports.specific_reports.reporting_rates import ReportingRates, ReportingDetails
from custom.ewsghana.reports.specific_reports.stock_status_report import ProductAvailabilityData
from custom.ewsghana.reports.stock_levels_report import FacilityReportData, StockLevelsLegend, InputStock, \
    FacilitySMSUsers, FacilityUsers, FacilityInChargeUsers, InventoryManagementData
from custom.ewsghana.utils import get_country_id


class DashboardReport(MultiReport):

    fields = [EWSLocationFilter, DatespanFilter]
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
                    FacilitySMSUsers(config),
                    FacilityUsers(config),
                    FacilityInChargeUsers(config),
                    InventoryManagementData(config),
                    ProductSelectionPane(config)
                ]
        self.split = False
        return [
            ProductAvailabilityData(config=self.report_config),
            ReportingRates(config=self.report_config),
            ReportingDetails(config=self.report_config)
        ]
