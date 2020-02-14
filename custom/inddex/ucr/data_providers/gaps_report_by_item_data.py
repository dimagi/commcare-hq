from memoized import memoized

from custom.inddex.ucr.data_providers.mixins import GapsByItemReportDataMixin


class GapsReportByItemSummaryData(GapsByItemReportDataMixin):
    total_row = None
    title = 'Gaps By Item Summary'
    slug = 'gaps_by_item_summary'
    headers_in_order = [
        'food_code', 'food_name', 'fao_who_gift_food_group_code', 'fao_who_gift_food_group_desc',
        'user_food_group', 'food_type', 'number_of_occurrences', 'conv_factor_gap_code',
        'conv_factor_gap_desc', 'fct_gap_code', 'fct_gap_desc'
    ]

    def __init__(self, config):
        super().__init__()
        self.config = config

    @property
    @memoized
    def rows(self):
        rows = super().rows
        self._append_number_of_occurrences(rows)

        return self.rearrange_data(rows)

    @staticmethod
    def _append_number_of_occurrences(data):
        occurrences = {}
        for record in data:
            food_code = record['data']['food_code']
            if food_code not in occurrences:
                occurrences[food_code] = 1
            else:
                occurrences[food_code] += 1

        for record in data:
            food_code = record['data']['food_code']
            if food_code in occurrences:
                record['data']['number_of_occurrences'] = str(occurrences[food_code])


class GapsReportByItemDetailsData(GapsByItemReportDataMixin):
    total_row = None
    title = 'Gaps By Item Details'
    slug = 'gaps_by_item_details'
    headers_in_order = [
        'gap_type', 'gap_code', 'gap_desc', 'food_type', 'caseid', 'food_code', 'food_name', 'short_name',
        'eating_occasion', 'time_block', 'fao_who_gift_food_group_code', 'fao_who_gift_food_group_desc',
        'user_food_group', 'food_base_term', 'tag_1', 'other_tag_1', 'tag_2', 'other_tag_2', 'tag_3',
        'other_tag_3', 'tag_4', 'other_tag_4', 'tag_5', 'other_tag_5', 'tag_6', 'other_tag_6', 'tag_7',
        'other_tag_7', 'tag_8', 'other_tag_8', 'tag_9', 'other_tag_9', 'tag_10', 'conv_method',
        'conv_method_desc', 'conv_option', 'conv_option_desc', 'conv_size', 'conv_units', 'quantity',
        'nsr_conv_method_code_post_cooking', 'nsr_conv_method_desc_post_cooking',
        'nsr_conv_option_code_post_cooking', 'nsr_conv_option_desc_post_cooking', 'nsr_conv_size_post_cooking',
        'nsr_consumed_cooked_fraction', 'conv_factor_used', 'conv_factor_food_code',
        'conv_factor_base_term_food_code', 'fct_data_used', 'fct_food_code_exists',
        'fct_base_term_food_code_exists', 'fct_reference_food_code_exists', 'base_term_food_code',
        'reference_food_code', 'unique_respondent_id', 'recall_case_id', 'opened_by_username',
        'owner_name', 'recall_date'
    ]

    def __init__(self, config):
        super().__init__()
        self.config = config

    @property
    @memoized
    def rows(self):
        rows = super().rows
        self._append_gap_information(rows)

        return self.rearrange_data(rows)

    @staticmethod
    def _append_gap_information(data):

        def split_record():
            gap_conv = record['data']['conv_factor_gap_code']
            gap_fct = record['data']['fct_gap_code']
            elements = []
            for gap in [(gap_conv, 'conv_factor'), (gap_fct, 'fct')]:
                if gap[0]:
                    copy = record.copy()
                    copy['data'].update(
                        gap_type=gap[1],
                        gap_code=copy[f'{gap[1]}_gap_code'],
                        gap_desc=copy[f'{gap[1]}_gap_desc']
                    )
                    elements.append(copy)
                else:
                    elements.append(None)

            return elements

        for record in data.copy():
            for element in split_record():
                if element:
                    data.append(element)
            data.pop(data.index(record))
