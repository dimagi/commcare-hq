from custom.ewsghana.comparison_report import ProductsCompareReport, LocationsCompareReport,\
    SMSUsersCompareReport, WebUsersCompareReport, SupplyPointsCompareReport

from custom.ewsghana.reports.StockLevelsReport import StockLevelsReport

TEST = True
LOCATION_TYPES = ["country", "region", "district", "facility"]

CUSTOM_REPORTS = (
    ('Custom reports', (
        StockLevelsReport,
        ProductsCompareReport,
        LocationsCompareReport,
        SupplyPointsCompareReport,
        WebUsersCompareReport,
        SMSUsersCompareReport
    )),
)
