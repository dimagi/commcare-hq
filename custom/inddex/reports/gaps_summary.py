from memoized import memoized

from custom.inddex import filters
from custom.inddex.ucr.data_providers.gaps_summary_data import (
    ConvFactorGapsSummaryData,
    FCTGapsSummaryData,
)
from custom.inddex.utils import MultiTabularReport


class GapsSummaryReport(MultiTabularReport):
    name = 'Output 2a - Gaps Summary by Food Type'
    slug = 'gaps_summary'

    @property
    def fields(self):
        return [
            filters.CaseOwnersFilter,
            filters.DateRangeFilter,
            filters.GapTypeFilter,
            filters.RecallStatusFilter,
        ]

    @property
    @memoized
    def data_providers(self):
        return [
            ConvFactorGapsSummaryData(config=self.report_config),
            FCTGapsSummaryData(config=self.report_config)
        ]

    @property
    def report_config(self):
        report_config = {}  # TODO port to FoodData.from_request
        report_config.update(
            gap_type=self.request.GET.get('gap_type') or '',
            recall_status=self.request.GET.get('recall_status') or '',
        )
        return report_config
