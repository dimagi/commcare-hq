from memoized import memoized

from custom.inddex.ucr.data_providers.gaps_summary_data import (
    ConvFactorGapsSummaryData,
    FCTGapsSummaryData
)
from custom.inddex.utils import BaseGapsSummaryReport


class GapsSummaryByFoodTypeSummaryReport(BaseGapsSummaryReport):
    title = '1a: Gaps Report Summary by Food Type'
    name = title
    slug = 'gaps_report_summary_by_food_type'
    export_only = False
    show_filters = True

    @property
    @memoized
    def data_providers(self):
        return [
            ConvFactorGapsSummaryData(config=self.report_config),
            FCTGapsSummaryData(config=self.report_config)
        ]
