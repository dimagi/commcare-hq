from memoized import memoized

from custom.inddex.ucr.data_providers.nutrient_intakes_data import NutrientIntakesByFoodData, \
    NutrientIntakesByRespondentData
from custom.inddex.utils import MultiTabularReport, ReportBaseMixin


class NutrientIntakesReport(MultiTabularReport, ReportBaseMixin):
    title = '2: Nutrient Intakes by Food and by Respondent'
    name = title
    slug = 'nutrient_intakes_by_food_and_by_respondent'
    export_only = False
    show_filters = True

    @property
    def report_context(self):
        context = super().report_context
        context['export_only'] = self.export_only

        return context

    @property
    def fields(self):
        return self.get_base_fields()

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        filters_config = self.get_base_report_config(self)
        return [
            NutrientIntakesByFoodData(config=config, filters_config=filters_config),
            NutrientIntakesByRespondentData(config=config, filters_config=filters_config)
        ]
