from custom.ilsgateway.tanzania.reports.alerts import AlertReport
from custom.ilsgateway.tanzania.reports.dashboard_report import DashboardReport
from custom.ilsgateway.tanzania.reports.delivery import DeliveryReport
from custom.ilsgateway.tanzania.reports.randr import RRreport
from custom.ilsgateway.tanzania.reports.facility_details import FacilityDetailsReport
from custom.ilsgateway.tanzania.reports.stock_on_hand import StockOnHandReport
from custom.ilsgateway.tanzania.reports.supervision import SupervisionReport


CUSTOM_REPORTS = (
    ('Custom reports', (
        DashboardReport,
        AlertReport,
        StockOnHandReport,
        RRreport,
        FacilityDetailsReport,
        DeliveryReport,
        SupervisionReport,
    )),
)

# For QA purposes it should be set to true.
TEST = True
