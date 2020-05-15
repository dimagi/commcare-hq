import textwrap
from collections import defaultdict

from custom.inddex import filters
from custom.inddex.const import (
    FOOD_ITEM,
    NON_STANDARD_FOOD_ITEM,
    NON_STANDARD_RECIPE,
    STANDARD_RECIPE,
    ConvFactorGaps,
    FctGaps,
)
from custom.inddex.food import FoodData

from .utils import MultiTabularReport, format_row


class GapsSummaryReport(MultiTabularReport):
    name = 'Output 2a - Gaps Summary by Food Type'
    slug = 'report_2a_gaps_summary_by_food_type'
    description = textwrap.dedent("""
        This output includes summaries of the existing conversion factor gaps
        and FCT gaps in the recall data.It provides researchers with an
        overview of the number of data gaps that must be addressed before the
        recall data can be analyzed. Information in this output is
        disaggregated by food type.
    """)

    @property
    def fields(self):
        return [
            filters.CaseOwnersFilter,
            filters.DateRangeFilter,
            filters.GapTypeFilter,
            filters.RecallStatusFilter,
        ]

    @property
    def data_providers(self):
        cf_gaps_data, fct_gaps_data = get_gaps_data(self.domain, self.request)
        return [cf_gaps_data, fct_gaps_data]


def get_gaps_data(domain, request):
    cf_gaps = defaultdict(int)
    fct_gaps = defaultdict(int)
    food_data = FoodData.from_request(domain, request)
    for row in food_data.rows:
        cf_gaps[(row.conv_factor_gap_code, row.food_type or '')] += 1
        fct_gaps[(row.fct_gap_code, row.food_type or '')] += 1

    return (
        ConvFactorGapsData(cf_gaps),
        FctGapsData(fct_gaps),
    )


class GapsData:
    def __init__(self, gaps):
        self._gaps = gaps

    @property
    def rows(self):
        for gap_code in self._gaps_descriptions:
            for food_type in [FOOD_ITEM, NON_STANDARD_FOOD_ITEM, STANDARD_RECIPE, NON_STANDARD_RECIPE]:
                description = self._gaps_descriptions[gap_code]
                count = self._gaps.get((gap_code, food_type), 0)
                yield format_row([gap_code, description, food_type, count])


class ConvFactorGapsData(GapsData):
    title = 'Conv Factor Gaps Summary'
    slug = 'conv_factor_gaps_summary'
    _gaps_descriptions = ConvFactorGaps.DESCRIPTIONS

    @property
    def headers(self):
        return ['conv_factor_gap_code', 'conv_factor_gap_desc', 'food_type', 'conv_gap_food_type_total']


class FctGapsData(GapsData):
    title = 'FCT Gaps Summary'
    slug = 'fct_gaps_summary'
    _gaps_descriptions = FctGaps.DESCRIPTIONS

    @property
    def headers(self):
        return ['fct_gap_code', 'fct_gap_desc', 'food_type', 'fct_gap_food_type_total']
