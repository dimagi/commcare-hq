from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from custom.ewsghana.reports.base_report import MultiReport
from dimagi.utils.decorators.memoized import memoized


class StockLevelsReport(MultiReport):
    title = "Stock Levels Report"
    fields = [AsyncLocationFilter, MonthFilter, YearFilter]
    name = "Stock Levels Report"
    slug = 'ews_stock_levels_report'

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return []