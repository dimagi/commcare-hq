from memoized import memoized

from custom.inddex.filters import GapTypeFilter, RecallStatusFilter
from custom.inddex.ucr.data_providers.gaps_summary_data import (
    GapsSummaryMasterOutputData,
    ConvFactorGapsSummaryData,
    FCTGapsSummaryData
)
from custom.inddex.utils import MultiTabularReport


class GapsSummaryByFoodTypeReport(MultiTabularReport):
    title = '1a: Gaps Report Summary by Food Type'
    name = title
    slug = 'gaps_report_summary_by_food_type'
    export_only = False
    show_filters = True

    @property
    def fields(self):
        return [
            GapTypeFilter,
            RecallStatusFilter
        ]

    @property
    def report_context(self):
        context = super().report_context
        context['export_only'] = self.export_only

        return context

    @property
    def recall_status(self):
        return self.request.GET.get('recall_status') or ''

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        filters_config = {
            'recall_status': self.recall_status
        }

        return [
            GapsSummaryMasterOutputData(config=config, filters_config=filters_config),
            ConvFactorGapsSummaryData(config=config, filters_config=filters_config),
            FCTGapsSummaryData(config=config, filters_config=filters_config)
        ]
