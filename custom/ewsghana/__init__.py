from custom.ewsghana.reports.email_reports import CMSRMSReport, StockSummaryReport
from custom.ewsghana.reports.maps import EWSMapReport
from custom.ewsghana.reports.stock_levels_report import StockLevelsReport
from custom.ewsghana.reports.specific_reports.dashboard_report import DashboardReport
from custom.ewsghana.reports.specific_reports.stock_status_report import StockStatus
from custom.ewsghana.reports.specific_reports.reporting_rates import ReportingRatesReport
from custom.ewsghana.reports.stock_transaction import StockTransactionReport

LOCATION_TYPES = ["country", "region", "district", "facility"]

CUSTOM_DASHBOARD_VIEW_NAME = 'dashboard_page'

CUSTOM_REPORTS = (
    ('Custom reports', (
        DashboardReport,
        StockStatus,
        StockLevelsReport,
        ReportingRatesReport,
        EWSMapReport,
        CMSRMSReport,
        StockSummaryReport,
        StockTransactionReport
    )),
)

ROOT_SITE_CODE = 'ghana'
