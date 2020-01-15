from memoized import memoized

from custom.inddex.ucr.data_providers.gaps_summary_data import GapsSummaryMasterOutputData, ConvFactorGapsSummaryData, \
    FCTGapsSummaryData
from custom.inddex.ucr.report_bases.gaps_summary_report import GapsSummaryByFoodTypeBase
from custom.inddex.ucr.report_bases.mixins import GapsSummaryFoodTypeBaseMixin


class GapsSummaryByFoodTypeReport(GapsSummaryByFoodTypeBase, GapsSummaryFoodTypeBaseMixin):

    @property
    def fields(self):
        return self.get_base_fields()

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        filters_config = self.get_base_report_config(self)
        return [
            GapsSummaryMasterOutputData(config=config, filters_config=filters_config),
            ConvFactorGapsSummaryData(config=config, filters_config=filters_config),
            FCTGapsSummaryData(config=config, filters_config=filters_config)
        ]
