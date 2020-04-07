from memoized import memoized

from custom.inddex.filters import (
    AgeRangeFilter,
    BreastFeedingFilter,
    FaoWhoGiftFoodGroupDescriptionFilter,
    GapTypeFilter,
    GenderFilter,
    PregnancyFilter,
    RecallStatusFilter,
    SettlementAreaFilter,
    SupplementsFilter,
)
from custom.inddex.ucr.data_providers.nutrient_intakes_data import (
    NutrientIntakesByFoodData,
    NutrientIntakesByRespondentData,
)
from custom.inddex.utils import MultiTabularReport


class NutrientIntakeReport(MultiTabularReport):
    title = 'Output 3 - Disaggregated Intake Data by Food and Aggregated Daily Intake Data by Respondent'
    name = title
    slug = 'nutrient_intake'
    export_only = True
    show_filters = True

    @property
    def fields(self):
        return super().fields + [
            GenderFilter,
            AgeRangeFilter,
            PregnancyFilter,
            BreastFeedingFilter,
            SettlementAreaFilter,
            SupplementsFilter,
            FaoWhoGiftFoodGroupDescriptionFilter,
            RecallStatusFilter,
        ]

    @property
    def report_config(self):
        report_config = super().report_config
        request_slugs = [
            'gender',
            'age_range',
            'pregnant',
            'breastfeeding',
            'urban_rural',
            'supplements',
            'recall_status',
            'fao_who_gift_food_group_description',
        ]
        report_config.update({slug: self.request.GET.get(slug, '')
                              for slug in request_slugs})
        return report_config

    @property
    @memoized
    def data_providers(self):
        return [
            NutrientIntakesByFoodData(config=self.report_config),
            NutrientIntakesByRespondentData(config=self.report_config)
        ]
