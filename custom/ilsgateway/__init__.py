from custom.ilsgateway.comparison_reports import ProductsCompareReport, LocationsCompareReport, \
    WebUsersCompareReport, SMSUsersCompareReport, ProductAvailabilityReport
from custom.ilsgateway.tanzania.reports.alerts import AlertReport
from custom.ilsgateway.tanzania.reports.dashboard_report import DashboardReport
from custom.ilsgateway.tanzania.reports.delivery import DeliveryReport
from custom.ilsgateway.tanzania.reports.randr import RRreport
from custom.ilsgateway.tanzania.reports.facility_details import FacilityDetailsReport
from custom.ilsgateway.tanzania.reports.stock_on_hand import StockOnHandReport
from custom.ilsgateway.tanzania.reports.supervision import SupervisionReport
from custom.ilsgateway.tanzania.reports.unrecognized_sms import UnrecognizedSMSReport


CUSTOM_REPORTS = (
    ('Custom reports', (
        DashboardReport,
        AlertReport,
        StockOnHandReport,
        RRreport,
        FacilityDetailsReport,
        DeliveryReport,
        SupervisionReport,
        UnrecognizedSMSReport,
        ProductsCompareReport,
        LocationsCompareReport,
        WebUsersCompareReport,
        SMSUsersCompareReport,
        ProductAvailabilityReport
    )),
)

LOCATION_TYPES = ["MOHSW", "MSDZONE", "REGION", "DISTRICT", "FACILITY"]

PRODUCTS_CODES_PROGRAMS_MAPPING = {
    "Reproductive Health": ['dp', 'ip', 'cc', 'id', 'pp', 'cond'],
    "Anti-Malaria": ['al', 'sp', 'qi'],
    "Essential Medicine": ['ab', 'bp', 'ca', 'cp', 'dx', 'fs', 'md', 'os', 'pc', 'zs'],
    "Safe Motherhood": ['eo', 'ff']
}
