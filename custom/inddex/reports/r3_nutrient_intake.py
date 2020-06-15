import textwrap
from itertools import chain

from corehq.apps.reports.filters.case_list import CaseListFilter
from custom.inddex import filters
from custom.inddex.food import FoodData

from .utils import MultiTabularReport, format_row, na_for_None


class NutrientIntakeReport(MultiTabularReport):
    name = 'Report 3 - Disaggregated Intake Data by Respondent and Aggregated Daily Intake Data by Respondent'
    slug = 'report_3_disaggr_intake_data_by_rspndnt_and_aggr_daily_intake_data_by_rspndnt'  # yup, really

    export_only = True
    description = textwrap.dedent("""
        This report provides information on the total quantity and total
        nutrient content for each individual food or recipe reported by each
        respondent in the recall. It also provides total daily energy and
        nutrient intakes for each respondent. This report cannot be previewed.
        Users must download the data to access the information.
    """)

    @property
    def fields(self):
        return [
            CaseListFilter,
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


class IntakeData:
    title = 'Disaggregated Intake Data By Food'
    slug = 'disaggr_intake_data_by_rspndnt'
    _columns = [
        'unique_respondent_id', 'location_id', 'respondent_id',
        'recall_case_id', 'opened_by_username', 'owner_name', 'visit_date',
        'recall_status', 'gender', 'age_years_calculated',
        'age_months_calculated', 'age_range', 'pregnant', 'breastfeeding',
        'urban_rural', 'supplements', 'food_code', 'food_name', 'recipe_name',
        'caseid', 'food_type', 'reference_food_code', 'base_term_food_code',
        'include_in_analysis', 'fao_who_gift_food_group_code',
        'fao_who_gift_food_group_description', 'user_food_group',
        'is_ingredient', 'ingredient_type', 'total_grams',
        'conv_factor_gap_code', 'conv_factor_gap_desc', 'fct_gap_code',
        'fct_gap_desc'
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
                (na_for_None(row.get_nutrient_amt(name)) for name in self._nutrient_names),
            ))


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
        'visit_date',
        'recall_status',
        'gender',
        'age_years_calculated',
        'age_months_calculated',
        'age_range',
        'pregnant',
        'breastfeeding',
        'urban_rural',
        'supplements',
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
            key = (row.unique_respondent_id, row.visit_date)
            if key not in rows:
                rows[key] = {
                    'static_cols': [getattr(row, col) for col in self._metadata_columns],
                    'nutrients': nutrients
                }
            else:
                rows[key]['nutrients'] = map(_sum, zip(rows[key]['nutrients'], nutrients))

        for row in rows.values():
            yield format_row(chain(row['static_cols'], map(na_for_None, row['nutrients'])))


def _sum(items):
    return sum(filter(None, items))
