from custom.ewsghana.comparison_report import ProductsCompareReport, LocationsCompareReport,\
    SMSUsersCompareReport, WebUsersCompareReport

from custom.ewsghana.reports.StockLevelsReport import StockLevelsReport

TEST = True
LOCATION_TYPES = ["country", "region", "district", "facility"]

CUSTOM_REPORTS = (
    ('Custom reports', (
        StockLevelsReport,
        ProductsCompareReport,
        LocationsCompareReport,
        WebUsersCompareReport,
        SMSUsersCompareReport
    )),
)
