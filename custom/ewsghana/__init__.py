from custom.ewsghana.comparison_report import ProductsCompareReport, LocationsCompareReport,\
    SMSUsersCompareReport, WebUsersCompareReport
from custom.ewsghana.reports.specific_reports.stock_status_report import StockStatus
from custom.ewsghana.reports.stock_levels_report import StockLevelsReport

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
