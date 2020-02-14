from memoized import memoized

from custom.inddex.ucr.data_providers.mixins import GapsReportDataMixin


def get_filtered_data(data, conv=False):
    if conv:
        pattern = {
            ('1', 'conversion factor available'): {
                'food_item': 0, 'non_std_food_item': 0, 'std_recipe': 0, 'non_std_recipe': 0
            },
            ('2', 'using conversion factor from base term food code'): {
                'food_item': 0, 'non_std_food_item': 0, 'std_recipe': 0, 'non_std_recipe': 0
            },
            ('8', 'no conversion factor available'): {
                'food_item': 0, 'non_std_food_item': 0, 'std_recipe': 0, 'non_std_recipe': 0
            },
        }
    else:
        pattern = {
            ('1', 'fct data available'): {
                'food_item': 0, 'non_std_food_item': 0, 'std_recipe': 0, 'non_std_recipe': 0
            },
            ('2', 'using fct data from base term food code'): {
                'food_item': 0, 'non_std_food_item': 0, 'std_recipe': 0, 'non_std_recipe': 0
            },
            ('3', 'using fct data from reference food code'): {
                'food_item': 0, 'non_std_food_item': 0, 'std_recipe': 0, 'non_std_recipe': 0
            },
            ('7', 'ingredient(s) contain fct data gaps'): {
                'food_item': 0, 'non_std_food_item': 0, 'std_recipe': 0, 'non_std_recipe': 0
            },
            ('8', 'no fct data available'): {
                'food_item': 0, 'non_std_food_item': 0, 'std_recipe': 0, 'non_std_recipe': 0
            },
        }

    for record in data:
        if conv:
            if not record['data'].get('conv_factor_gap_code'):
                return None
            key = (record['data']['conv_factor_gap_code'], record['data']['conv_factor_gap_desc'])
            pattern[key][record['data']['food_type']] += 1
        else:
            if not record['data'].get('fct_gap_code'):
                return None
            key = (record['data']['fct_gap_code'], record['data']['fct_gap_desc'])
            pattern[key][record['data']['food_type']] += 1

    return pattern


class ConvFactorGapsSummaryData(GapsReportDataMixin):
    title = 'Conv Factor Gaps Summary'
    slug = 'conv_factor_gaps_summary'
    headers_in_order = ['conv_factor_gap_code', 'conv_factor_gap_desc', 'food_type', 'conv_gap_food_type_total']

    def __init__(self, config):
        self.config = config

    @property
    @memoized
    def rows(self):
        rows = super().rows
        filtered_data = get_filtered_data(rows, conv=True)
        result = []
        if not filtered_data:
            return result

        for key in filtered_data:
            for food_type in filtered_data[key]:
                result.append([key[0], key[1], food_type, filtered_data[key][food_type]])

        return result


class FCTGapsSummaryData(GapsReportDataMixin):
    title = 'FCT Gaps Summary'
    slug = 'fct_gaps_summary'
    headers_in_order = ['fct_gap_code', 'fct_gap_desc', 'food_type', 'fct_gap_food_type_total']

    def __init__(self, config):
        self.config = config

    @property
    @memoized
    def rows(self):
        rows = super().rows
        filtered_data = get_filtered_data(rows)
        result = []
        if not filtered_data:
            return result

        for key in filtered_data:
            for food_type in filtered_data[key]:
                result.append([key[0], key[1], food_type, filtered_data[key][food_type]])

        return result
