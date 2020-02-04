from memoized import memoized

from custom.inddex.ucr.data_providers.mixins import GapsReportSummaryDataMixin


class ConvFactorGapsSummaryData(GapsReportSummaryDataMixin):
    title = 'Conv Factor Gaps Summary by Food Type'
    slug = 'conv_factor_gaps_summary_by_food_type'
    headers_in_order = ['conv_factor_gap_code', 'conv_factor_gap_desc', 'food_type', 'conv_gap_food_type_total']

    def __init__(self, config):
        self.config = config

    @property
    @memoized
    def rows(self):
        return [
            [1, 'conv factor available', 'food_item', 600],
            [1, 'conv factor available', 'non_std_food', 0],
            [1, 'conv factor available', 'std_recipe', 300],
            [1, 'conv factor available', 'non_std_recipe', 0],
            [2, 'using conversion factor from base term food code', 'food_item', 250],
            [2, 'using conversion factor from base term food code', 'non_std_food', 0],
            [2, 'using conversion factor from base term food code', 'std_recipe', 0],
            [2, 'using conversion factor from base term food code', 'non_std_recipe', 0],
            [8, 'no conversion factor available', 'food_item', 150],
            [8, 'no conversion factor available', 'non_std_food', 50],
            [8, 'no conversion factor available', 'std_recipe', 200],
            [8, 'no conversion factor available', 'non_std_recipe', 65],
            [9, 'not applicable', 'food_item', 0],
            [9, 'not applicable', 'non_std_food', 0],
            [9, 'not applicable', 'std_recipe', 0],
            [9, 'not applicable', 'non_std_recipe', 0]
        ]


class FCTGapsSummaryData(GapsReportSummaryDataMixin):
    title = 'FCT Gaps Summary by Food Type'
    slug = 'fct_gaps_summary_by_food_type'
    headers_in_order = ['fct_gap_code', 'fct_gap_desc', 'food_type', 'fct_gap_food_type_total']

    def __init__(self, config):
        self.config = config

    @property
    @memoized
    def rows(self):
        return [
            [1, 'fct data available', 'food_item', 600],
            [1, 'fct data available', 'non_std_food', 0],
            [1, 'fct data available', 'std_recipe', 300],
            [1, 'fct data available', 'non_std_recipe', 0],
            [2, 'using fct data from base term food code', 'food_item', 270],
            [2, 'using fct data from base term food code', 'non_std_food', 0],
            [2, 'using fct data from base term food code', 'std_recipe', 0],
            [2, 'using fct data from base term food code', 'non_std_recipe', 0],
            [3, 'using fct data from reference food code', 'food_item', 250],
            [3, 'using fct data from reference food code', 'non_std_food', 0],
            [3, 'using fct data from reference food code', 'std_recipe', 0],
            [3, 'using fct data from reference food code', 'non_std_recipe', 0],
            [4, 'ingredient(s) using fct data from base term food code', 'food_item', 0],
            [4, 'ingredient(s) using fct data from base term food code', 'non_std_food', 0],
            [4, 'ingredient(s) using fct data from base term food code', 'std_recipe', 25],
            [4, 'ingredient(s) using fct data from base term food code', 'non_std_recipe', 36],
            [8, 'no fct data available', 'food_item', 222],
            [8, 'no fct data available', 'non_std_food', 50],
            [8, 'no fct data available', 'std_recipe', 0],
            [8, 'no fct data available', 'non_std_recipe', 65],
            [9, 'not applicable', 'food_item', 0],
            [9, 'not applicable', 'non_std_food', 0],
            [9, 'not applicable', 'std_recipe', 0],
            [9, 'not applicable', 'non_std_recipe', 0],
        ]
