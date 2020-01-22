from memoized import memoized

from custom.inddex.ucr.data_providers.nutrient_intakes_data import NutrientIntakesByFoodData, \
    NutrientIntakesByRespondentData
from custom.inddex.ucr.report_bases.nutrient_intakes_report import NutrientIntakesReportBase
from custom.inddex.ucr.report_bases.mixins import NutrientIntakesBaseMixin


class NutrientIntakesReport(NutrientIntakesReportBase, NutrientIntakesBaseMixin):

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
