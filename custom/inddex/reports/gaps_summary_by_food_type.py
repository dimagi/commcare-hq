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
    report_comment = 'This output includes summaries of the existing conversion factor gaps and FCT gaps in the ' \
                     'recall data.It provides researchers with an overview of the number of data gaps that must ' \
                     'be addressed before the recall data can be analyzed. Information in this output is ' \
                     'disaggregated by food type.'

    @property
    @memoized
    def data_providers(self):
        return [
            ConvFactorGapsSummaryData(config=self.report_config),
            FCTGapsSummaryData(config=self.report_config)
        ]
