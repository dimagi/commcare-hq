import textwrap
from itertools import chain

from corehq.apps.reports.filters.case_list import CaseListFilter
from custom.inddex import filters
from custom.inddex.food import INDICATORS, FoodData

from .utils import MultiTabularReport, format_row, na_for_None


class MasterDataReport(MultiTabularReport):
    name = 'Report 1 - Master Data File'
    slug = 'report_1_master_data_file'
    export_only = True
    description = textwrap.dedent("""
        This report includes all data that appear in the reports as well as
        background data that are used to perform report calculations.
    """)

    @property
    def fields(self):
        return [
            CaseListFilter,
            filters.DateRangeFilter,
            filters.GapTypeFilter,
            filters.RecallStatusFilter
        ]

    @property
    def data_providers(self):
        food_data = FoodData.from_request(self.domain, self.request)
        return [MasterData(food_data)]


class MasterData:
    title = "master_data"
    slug = title

    def __init__(self, food_data):
        self._food_data = food_data

    @property
    def headers(self):
        return [i.slug for i in INDICATORS] + list(self._get_nutrient_headers())

    @property
    def rows(self):
        for row in self._food_data.rows:
            static_cols = (getattr(row, column.slug) for column in INDICATORS)
            nutrient_cols = self._get_nutrient_values(row)
            yield format_row(chain(static_cols, nutrient_cols))

    def _get_nutrient_headers(self):
        for name in self._food_data.fixtures.nutrient_names:
            yield f"{name}_per_100g"
            yield name

    def _get_nutrient_values(self, row):
        for name in self._food_data.fixtures.nutrient_names:
            yield na_for_None(row.get_nutrient_per_100g(name))
            yield na_for_None(row.get_nutrient_amt(name))
