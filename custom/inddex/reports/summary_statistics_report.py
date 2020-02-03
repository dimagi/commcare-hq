from memoized import memoized

from custom.inddex.ucr.data_providers.summary_statistics_data import (
    SummaryStatsNutrientDataProvider,
)
from custom.inddex.utils import BaseNutrientReport


class SummaryStatisticsReport(BaseNutrientReport):
    title = '3: Summary Statistics Report'
    name = title
    slug = 'summary_statistics_report'

    @property
    def report_config(self):
        report_config = super().report_config
        report_config.update(self.filters_config)
        return report_config

    @property
    @memoized
    def data_providers(self):
        return [
            SummaryStatsNutrientDataProvider(config=self.report_config)
        ]
