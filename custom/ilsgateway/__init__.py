from custom.ilsgateway.reports.alerts import AlertReport
from custom.ilsgateway.reports.dashboard_report import DashboardReport
from custom.ilsgateway.reports.randr import RRreport
from custom.ilsgateway.reports.stock_on_hand import StockOnHandReport
CUSTOM_REPORTS = (
    ('Custom reports', (
        DashboardReport,
        AlertReport,
        StockOnHandReport,
        RRreport
    )),
)
