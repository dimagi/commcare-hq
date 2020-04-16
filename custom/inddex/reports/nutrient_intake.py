from itertools import chain

from custom.inddex import filters
from custom.inddex.food import FoodData

from .utils import MultiTabularReport, format_row


class NutrientIntakeReport(MultiTabularReport):
    name = 'Output 3 - Disaggregated Intake Data by Food and Aggregated Daily Intake Data by Respondent'
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
    def data_providers(self):
        food_data = FoodData.from_request(self.domain, self.request)
        return [
            IntakeData(food_data),
            DailyIntakeData(food_data),
        ]


class DailyIntakeData:
    title = 'Aggregated Daily Intake By Respondent'
    slug = 'aggr_daily_intake_by_rspndnt'
    _metadata_columns = [
        'unique_respondent_id',
        'location_id',
        'respondent_id',
        'recall_case_id',
        'opened_by_username',
        'owner_name',
        'recalled_date',
        'recall_status',
        'gender',
        'age_years_calculated',
        'age_months_calculated',
        'age_range',
        'supplements',
        'urban_rural',
        'pregnant',
        'breastfeeding',
    ]

    def __init__(self, food_data):
        self._food_data = food_data
        self._nutrient_names = self._food_data.fixtures.nutrient_names

    @property
    def headers(self):
        return self._metadata_columns + list(self._nutrient_names)

    @property
    def rows(self):
        rows = {}
        for row in self._food_data.rows:
            nutrients = [row.get_nutrient_amt(name) for name in self._nutrient_names]
            key = (row.unique_respondent_id, row.recalled_date)
            if key not in rows:
                rows[key] = {
                    'static_cols': [getattr(row, col) for col in self._metadata_columns],
                    'nutrients': nutrients
                }
            else:
                rows[key]['nutrients'] = map(_sum, zip(rows[key]['nutrients'], nutrients))

        for key, row in sorted(rows.items()):
            yield format_row(chain(row['static_cols'], row['nutrients']))


def _sum(items):
    return sum(filter(None, items))


class IntakeData:
    title = 'Disaggregated Intake Data By Food'
    slug = 'disaggr_intake_data_by_food'
    _columns = [
        'unique_respondent_id', 'location_id', 'respondent_id',
        'recall_case_id', 'opened_by_username', 'owner_name', 'recalled_date',
        'recall_status', 'gender', 'age_years_calculated',
        'age_months_calculated', 'age_range', 'supplements', 'urban_rural',
        'pregnant', 'breastfeeding', 'food_code', 'base_term_food_code',
        'reference_food_code', 'caseid', 'food_name', 'recipe_name',
        'fao_who_gift_food_group_code', 'fao_who_gift_food_group_description',
        'user_food_group', 'food_type', 'include_in_analysis', 'is_ingredient',
        'food_status', 'total_grams', 'conv_factor_gap_code',
        'conv_factor_gap_desc', 'fct_gap_code', 'fct_gap_desc',
    ]

    def __init__(self, food_data):
        self._food_data = food_data
        self._nutrient_names = self._food_data.fixtures.nutrient_names

    @property
    def headers(self):
        return self._columns + list(self._nutrient_names)

    @property
    def rows(self):
        for row in self._food_data.rows:
            yield format_row(chain(
                (getattr(row, col) for col in self._columns),
                (row.get_nutrient_amt(name) for name in self._nutrient_names),
            ))
