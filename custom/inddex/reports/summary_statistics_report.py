from memoized import memoized

from custom.inddex.ucr.data_providers.summary_statistics_data import SummaryStatsNutrientDataProvider
from custom.inddex.ucr.report_bases.mixins import ReportBaseMixin
from custom.inddex.ucr.report_bases.summary_statistics_report import SummaryStatisticsReportBase


class SummaryStatisticsReport(SummaryStatisticsReportBase, ReportBaseMixin):

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        filters_config = self.get_base_report_config(self)
        return [
            SummaryStatsNutrientDataProvider(config=config, filters_config=filters_config)
        ]
