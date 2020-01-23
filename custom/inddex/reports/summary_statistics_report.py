from memoized import memoized

from custom.inddex.ucr.data_providers.summary_statistics_data import SummaryStatsNutrientDataProvider
from custom.inddex.utils import MultiTabularReport, ReportBaseMixin


class SummaryStatisticsReport(MultiTabularReport, ReportBaseMixin):
    title = '3: Summary Statistics Report'
    name = title
    slug = 'summary_statistics_report'

    @property
    def fields(self):
        fields = super().fields
        fields += self.get_base_fields()

        return fields

    @property
    def report_config(self):
        report_config = super().report_config
        report_config.update(self.get_base_report_config(self))

        return report_config

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        filters_config = self.get_base_report_config(self)

        return [
            SummaryStatsNutrientDataProvider(config=config, filters_config=filters_config)
        ]
