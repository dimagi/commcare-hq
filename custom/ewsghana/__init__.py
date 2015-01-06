from custom.ewsghana.comparison_report import ProductsCompareReport, LocationsCompareReport,\
    SMSUsersCompareReport, WebUsersCompareReport
from custom.ewsghana.reports.StockLevelsReport import StockLevelsReport

CUSTOM_REPORTS = (
    ('Custom reports', (
        StockLevelsReport,
        ProductsCompareReport,
        LocationsCompareReport,
        WebUsersCompareReport,
        SMSUsersCompareReport
    )),
)
