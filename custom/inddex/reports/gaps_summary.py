from collections import defaultdict

from custom.inddex import filters
from custom.inddex.food import ConvFactorGaps, FctGaps, FoodData

from .utils import MultiTabularReport


class GapsSummaryReport(MultiTabularReport):
    name = 'Output 2a - Gaps Summary by Food Type'
    slug = 'gaps_summary'

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
        cf_gaps, fct_gaps = self._get_gap_counts()
        return [
            ConvFactorGapsData(cf_gaps),
            FctGapsData(fct_gaps),
        ]

    def _get_gap_counts(self):
        cf_gaps = defaultdict(int)
        fct_gaps = defaultdict(int)
        food_data = FoodData.from_request(self.domain, self.request)
        for row in food_data.rows:
            cf_gaps[(row.conv_factor_gap_code, row.food_type)] += 1
            fct_gaps[(row.fct_gap_code, row.food_type)] += 1
        return cf_gaps, fct_gaps


class GapsData:
    def __init__(self, gaps):
        self._gaps = gaps

    @property
    def rows(self):
        for (code, food_type), count in self._gaps.items():
            description = self._gaps_descriptions[code]
            yield [code, description, food_type, count]


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
