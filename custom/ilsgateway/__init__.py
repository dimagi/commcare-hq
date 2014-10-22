from custom.ilsgateway.reports.alerts import AlertReport
from custom.ilsgateway.reports.dashboard_report import DashboardReport

CUSTOM_REPORTS = (
    ('Custom reports', (
        DashboardReport,
        AlertReport,
    )),
)