from custom.ilsgateway.slab.views import SLABConfigurationReport
from custom.ilsgateway.tanzania.reports.alerts import AlertReport
from custom.ilsgateway.tanzania.reports.dashboard_report import DashboardReport
from custom.ilsgateway.tanzania.reports.delivery import DeliveryReport
from custom.ilsgateway.tanzania.reports.randr import RRreport
from custom.ilsgateway.tanzania.reports.facility_details import FacilityDetailsReport
from custom.ilsgateway.tanzania.reports.stock_on_hand import StockOnHandReport
from custom.ilsgateway.tanzania.reports.supervision import SupervisionReport
from custom.ilsgateway.tanzania.reports.unrecognized_sms import UnrecognizedSMSReport
from custom.ilsgateway.zipline.reports.supervisor_report import SupervisorReport
from custom.ilsgateway.zipline.reports.zipline_warehouse_order_report import ZiplineWarehouseOrderReport
from custom.ilsgateway.zipline.reports.zipline_warehouse_package_report import ZiplineWarehousePackageReport

CUSTOM_REPORTS = (
    ('Custom reports', (
        DashboardReport,
        AlertReport,
        StockOnHandReport,
        RRreport,
        FacilityDetailsReport,
        DeliveryReport,
        SupervisionReport,
        UnrecognizedSMSReport
    )),
    ('Slab', (
        SLABConfigurationReport,
    )),
    ('Zipline', (
        ZiplineWarehouseOrderReport,
        ZiplineWarehousePackageReport,
        SupervisorReport
    ),)
)

LOCATION_TYPES = ["MOHSW", "MSDZONE", "REGION", "DISTRICT", "FACILITY"]

PRODUCTS_CODES_PROGRAMS_MAPPING = {
    "Reproductive Health": ['dp', 'ip', 'cc', 'id', 'pp', 'cond'],
    "Anti-Malaria": ['al', 'sp', 'qi'],
    "Essential Medicine": ['ab', 'bp', 'ca', 'cp', 'dx', 'fs', 'md', 'os', 'pc', 'zs'],
    "Safe Motherhood": ['eo', 'ff']
}

LOGISTICS_PRODUCT_ALIASES = {
    'iucd': 'id',
    'depo': 'dp',
    'impl': 'ip',
    'coc': 'cc',
    'pop': 'pp'
}

ROOT_LOCATION_TYPE = 'MOHSW'

SLAB_DOMAIN = 'slab-tanzania'
