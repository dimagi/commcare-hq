from custom.inddex.filters import GapTypeFilter, GapDescriptionFilter, FoodTypeFilter, \
    RecallStatusFilter, FaoWhoGiftFoodGroupDescriptionFilter
from custom.inddex.ucr.data_providers.gaps_report_by_item_data import GapsReportByItemDetailsData, \
    GapsReportByItemSummaryData
from custom.inddex.utils import MultiTabularReport


class GapsReportByItem(MultiTabularReport):
    title = 'Output 2b - Detailed Information on Gaps'
    name = title
    slug = 'output_2b_detailed_information_on_gaps'
    report_comment = 'This output assists researchers in identifying incomplete or missing information in the ' \
                     'recall data. Researchers can use this output to view the specific items reported by ' \
                     'respondents that are missing conversion factor or food composition data. This output ' \
                     'also includes the information collected from the respondent during the recall. All gaps ' \
                     'in this report should be addressed before researchers conduct data analysis. Researchers ' \
                     'therefore should not download Outputs 3 and 4 unless all gaps in this report have ' \
                     'been addressed.'

    @property
    def fields(self):
        fields = super().fields
        fields += [
            GapTypeFilter,
            GapDescriptionFilter,
            FaoWhoGiftFoodGroupDescriptionFilter,
            FoodTypeFilter,
            RecallStatusFilter
        ]

        return fields

    @property
    def report_config(self):
        report_config = super().report_config
        report_config.update(
            fao_who_gift_food_group_description=self.fao_who_gift_food_group_description,
            gap_type=self.gap_type,
            gap_description=self.gap_description,
            food_type=self.food_type,
            recall_status=self.recall_status
        )

        return report_config

    @property
    def fao_who_gift_food_group_description(self):
        return self.request.GET.get('fao_who_gift_food_group_description') or ''

    @property
    def gap_type(self):
        return self.request.GET.get('gap_type') or ''

    @property
    def gap_description(self):
        return self.request.GET.get('gap_description') or ''

    @property
    def food_type(self):
        return self.request.GET.get('food_type') or ''

    @property
    def recall_status(self):
        return self.request.GET.get('recall_status') or ''

    @property
    def data_providers(self):
        return [
            GapsReportByItemSummaryData(config=self.report_config),
            GapsReportByItemDetailsData(config=self.report_config)
        ]
