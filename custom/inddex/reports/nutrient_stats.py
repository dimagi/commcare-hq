from custom.inddex import filters
from custom.inddex.food import FoodData

from .utils import MultiTabularReport


class NutrientStatsReport(MultiTabularReport):
    name = 'Output 4 - Nutrient Intake Summary Statistics'
    slug = 'nutrient_stats'
    is_released = False

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
            filters.RecallStatusFilter
        ]

    @property
    def data_providers(self):
        food_data = FoodData.from_request(self.domain, self.request)
        return [NutrientStatsData(food_data)]


class NutrientStatsData:
    title = 'Nutrient Intake Summary Stats'
    slug = 'nutr_intake_summary_stats'

    def __init__(self, food_data):
        self._food_data = food_data

    @property
    def headers(self):
        return [
            'nutrient', 'mean', 'median', 'std_dev', 'percentile_05',
            'percentile_25', 'percentile_50', 'percentile_75', 'percentile_95'
        ]

    @property
    def rows(self):
        return [
            ['energy_kcal', '125.8', '4.3', '177.0', '0.0', '0.0', '4.3', '190.7', '430.5'],
            ['water_g', '82.6', '26.3', '128.1', '0.0', '0.0', '26.3', '98.7', '312.1'],
            ['protein_g', '44.6', '31.6', '57.8', '0.0', '0.0', '31.6', '51.1', '145.5'],
            ['all_other_nutrients', '', '', '', '', '', '', '', ''],
        ]
