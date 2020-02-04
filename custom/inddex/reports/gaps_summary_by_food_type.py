from memoized import memoized

from custom.inddex.ucr.data_providers.gaps_summary_data import (
    ConvFactorGapsSummaryData,
    FCTGapsSummaryData
)
from custom.inddex.utils import BaseGapsSummaryReport


class GapsSummaryByFoodTypeSummaryReport(BaseGapsSummaryReport):
    title = 'Output 2a - Gaps Summary by Food Type'
    name = title
    slug = 'output_2a_gaps_summary_by_food_type'
    export_only = False
    show_filters = True

    @property
    @memoized
    def data_providers(self):
        return [
            ConvFactorGapsSummaryData(config=self.report_config),
            FCTGapsSummaryData(config=self.report_config)
        ]
