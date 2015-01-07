from custom.ewsghana.comparison_report import ProductsCompareReport, LocationsCompareReport,\
    SMSUsersCompareReport, WebUsersCompareReport
from custom.ewsghana.reports.StockLevelsReport import StockLevelsReport
from custom.ewsghana.reports.stock_status_report import StockStatus

CUSTOM_REPORTS = (
    ('Custom reports', (
        StockStatus,
        StockLevelsReport,
        ProductsCompareReport,
        LocationsCompareReport,
        WebUsersCompareReport,
        SMSUsersCompareReport
    )),
)
