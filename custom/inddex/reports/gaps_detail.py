from custom.inddex import filters
from custom.inddex.ucr.data_providers.gaps_report_by_item_data import (
    GapsReportByItemDetailsData,
    GapsReportByItemSummaryData,
)
from custom.inddex.utils import MultiTabularReport


class GapsDetailReport(MultiTabularReport):
    name = 'Output 2b - Detailed Information on Gaps'
    slug = 'gaps_detail'

    @property
    def fields(self):
        return [
            filters.CaseOwnersFilter,
            filters.DateRangeFilter,
            filters.GapTypeFilter,
            filters.GapDescriptionFilter,
            filters.FaoWhoGiftFoodGroupDescriptionFilter,
            filters.FoodTypeFilter,
            filters.RecallStatusFilter,
        ]


    @property
    def report_config(self):
        report_config = {}  # TODO port to FoodData.from_request
        report_config.update(
            gap_type=self.request.GET.get('gap_type') or '',
            recall_status=self.request.GET.get('recall_status') or '',
            fao_who_gift_food_group_description=self.fao_who_gift_food_group_description,
            gap_description=self.gap_description,
            food_type=self.food_type,
        )
        return report_config

    @property
    def fao_who_gift_food_group_description(self):
        return self.request.GET.get('fao_who_gift_food_group_description') or ''

    @property
    def gap_description(self):
        return self.request.GET.get('gap_description') or ''

    @property
    def food_type(self):
        return self.request.GET.get('food_type') or ''

    @property
    def data_providers(self):
        return [
            GapsReportByItemSummaryData(config=self.report_config),
            GapsReportByItemDetailsData(config=self.report_config)
        ]
