from memoized import memoized

from custom.inddex.filters import FaoWhoGiftFoodGroupDescriptionFilter
from custom.inddex.ucr.data_providers.nutrient_intakes_data import (
    NutrientIntakesByFoodData,
    NutrientIntakesByRespondentData,
)
from custom.inddex.utils import BaseNutrientReport


class NutrientIntakesReport(BaseNutrientReport):
    title = 'Output 3 - Disaggregated Intake Data by Food and Aggregated Daily Intake Data by Respondent'
    name = title
    slug = 'output_3_disaggr_intake_data_by_food_and_aggr_daily_intake_data_by_respondent'
    export_only = False
    show_filters = True

    @property
    def fields(self):
        fields = super().fields
        fields.insert(-1, FaoWhoGiftFoodGroupDescriptionFilter)
        return fields

    @property
    def report_context(self):
        context = super().report_context
        context['export_only'] = self.export_only
        return context

    @property
    def report_config(self):
        report_config = super().report_config
        report_config.update(self.filters_config)
        report_config.update(fao_who_gift_food_group_description=self.fao_who_gift_food_group_description)
        return report_config

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
