from memoized import memoized

from custom.inddex.ucr.data_providers.summary_statistics_data import (
    SummaryStatsNutrientDataProvider,
)
from custom.inddex.utils import BaseNutrientReport


class SummaryStatisticsReport(BaseNutrientReport):
    title = 'Output 4 - Nutrient Intake Summary Statistics'
    name = title
    slug = 'output_4_nutrient_intake_summary_statistics'
    report_comment = 'This output includes summary statistics for nutrient intakes reported during the recall ' \
                     '(mean, median, standard deviation, and percentiles). '

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
