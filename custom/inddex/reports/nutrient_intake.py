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
    def report_context(self):
        context = super().report_context
        context['export_only'] = self.export_only

        return context

    @property
    def report_config(self):
        report_config = super().report_config
        report_config.update(self._filters_config)
        report_config.update(
            fao_who_gift_food_group_description=self.fao_who_gift_food_group_description
        )
        return report_config

    @property
    def _filters_config(self):
        request_slugs = [
            'gender',
            'age_range',
            'pregnant',
            'breastfeeding',
            'urban_rural',
            'supplements',
            'recall_status',
        ]
        filters_config = super().report_config
        filters_config.update({slug: self.request.GET.get(slug, '') for slug in request_slugs})
        return filters_config

    @property
    def fao_who_gift_food_group_description(self):
        return self.request.GET.get('fao_who_gift_food_group_description') or ''

    @property
    @memoized
    def data_providers(self):
        return [
            NutrientIntakesByFoodData(config=self.report_config),
            NutrientIntakesByRespondentData(config=self.report_config)
        ]
