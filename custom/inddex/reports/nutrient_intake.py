from memoized import memoized

from custom.inddex import filters
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

    @property
    def fields(self):
        return [
            filters.CaseOwnersFilter,
            filters.DateRangeFilter,
            filters.GenderFilter,
            filters.AgeRangeFilter,
            filters.PregnancyFilter,
            filters.BreastFeedingFilter,
            filters.SettlementAreaFilter,
            filters.SupplementsFilter,
            filters.FaoWhoGiftFoodGroupDescriptionFilter,
            filters.RecallStatusFilter,
        ]

    @property
    def report_config(self):
        report_config = {}  # TODO port to FoodData.from_request
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
