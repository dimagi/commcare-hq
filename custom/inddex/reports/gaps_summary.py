from memoized import memoized

from custom.inddex.ucr.data_providers.gaps_summary_data import (
    ConvFactorGapsSummaryData,
    FCTGapsSummaryData
)
from custom.inddex.utils import BaseGapsSummaryReport


class GapsSummaryReport(BaseGapsSummaryReport):
    title = 'Output 2a - Gaps Summary by Food Type'
    name = title
    slug = 'gaps_summary'
    show_filters = True

    @property
    @memoized
    def data_providers(self):
        return [
            ConvFactorGapsSummaryData(config=self.report_config),
            FCTGapsSummaryData(config=self.report_config)
        ]
