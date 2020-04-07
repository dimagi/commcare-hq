from memoized import memoized

from custom.inddex.filters import GapTypeFilter, RecallStatusFilter
from custom.inddex.ucr.data_providers.gaps_summary_data import (
    ConvFactorGapsSummaryData,
    FCTGapsSummaryData,
)
from custom.inddex.utils import MultiTabularReport


class GapsSummaryReport(MultiTabularReport):
    title = 'Output 2a - Gaps Summary by Food Type'
    name = title
    slug = 'gaps_summary'
    show_filters = True

    @property
    def fields(self):
        return super().fields + [GapTypeFilter, RecallStatusFilter]

    @property
    @memoized
    def data_providers(self):
        return [
            ConvFactorGapsSummaryData(config=self.report_config),
            FCTGapsSummaryData(config=self.report_config)
        ]

    @property
    def report_config(self):
        report_config = super().report_config
        report_config.update(
            gap_type=self.request.GET.get('gap_type') or '',
            recall_status=self.request.GET.get('recall_status') or '',
        )
        return report_config
