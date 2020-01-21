from custom.inddex.ucr.report_bases.mixins import ReportBaseMixin
from custom.inddex.utils import MultiTabularReport


class SummaryStatisticsReportBase(ReportBaseMixin, MultiTabularReport):
    title = '3: Summary Statistics Report'
    name = '3: Summary Statistics Reports'
    slug = 'summary_statistics_report'

    @property
    def fields(self):
        fields = super(SummaryStatisticsReportBase, self).fields
        fields += self.get_base_fields()

        return fields

    @property
    def report_config(self):
        report_config = super(SummaryStatisticsReportBase, self).report_config
        report_config.update(self.get_base_report_config(self))

        return report_config

    @property
    def data_providers(self):
        raise super(SummaryStatisticsReportBase, self).data_providers


