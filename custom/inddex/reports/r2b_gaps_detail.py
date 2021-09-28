import textwrap

from corehq.apps.reports.filters.case_list import CaseListFilter
from custom.inddex import filters
from custom.inddex.const import ConvFactorGaps, FctGaps
from custom.inddex.food import FoodData

from .utils import MultiTabularReport, format_row


class GapsDetailReport(MultiTabularReport):
    name = 'Report 2b - Detailed Information on Gaps'
    slug = 'report_2b_detailed_information_on_gaps'
    is_released = False
    description = textwrap.dedent("""
        This report assists researchers in identifying incomplete or missing
        information in the recall data. Researchers can use this report to view
        the specific items reported by respondents that are missing conversion
        factor or food composition data. All gaps in this report should be
        addressed before researchers conduct data analysis. Researchers
        therefore should not download Reports 3 and 4 unless all gaps in this
        report have been addressed.
    """)

    @property
    def fields(self):
        return [
            CaseListFilter,
            filters.DateRangeFilter,
            filters.R2BGapFilter,
            filters.FaoWhoGiftFoodGroupDescriptionFilter,
            filters.FoodTypeFilter,
            filters.RecallStatusFilter,
        ]

    @property
    def data_providers(self):
        food_data = FoodData.from_request(self.domain, self.request)
        gaps_data = list(get_gaps_data(
            food_data,
            selected_gap_type=self.request.GET.get('2b_gap_type'),
            selected_gap_code=self.request.GET.get('2b_gap_code'),
        ))
        return [
            GapsByItemSummaryData(gaps_data),
            GapsDetailsData(gaps_data)
        ]


def _matches_filters(row, gap_class, gap_code, selected_gap_type, selected_gap_code):
    if selected_gap_type:
        if gap_class.slug != selected_gap_type:
            return False

        if selected_gap_code:
            gap_code = str(row.conv_factor_gap_code if selected_gap_type == ConvFactorGaps.slug
                           else row.fct_gap_code)
            return gap_code == selected_gap_code

    return True


def get_gaps_data(food_data, selected_gap_type=None, selected_gap_code=None):
    for row in food_data.rows:
        for gap_class, gap_code in [
                (ConvFactorGaps, row.conv_factor_gap_code),
                (FctGaps, row.fct_gap_code),
        ]:
            if _matches_filters(row, gap_class, gap_code, selected_gap_type, selected_gap_code):
                manually_set = ['gap_type', 'gap_code', 'gap_desc', 'number_occurrence']
                yield {
                    'gap_type': gap_class.name,
                    'gap_code': gap_code,
                    'gap_desc': gap_class.DESCRIPTIONS[gap_code],
                    **{col: getattr(row, col, None) for col in GapsDetailsData.headers
                    if col not in manually_set},
                }


class GapsByItemSummaryData:
    title = 'Gaps By Item Summary'
    slug = 'gaps_by_item_summary'
    headers = [
        'gap_type', 'gap_code', 'gap_desc', 'number_occurrence', 'food_code',
        'food_name', 'food_type', 'fao_who_gift_food_group_code',
        'fao_who_gift_food_group_description', 'user_food_group',
    ]

    def __init__(self, gaps_data):
        self._gaps_data = gaps_data

    @property
    def rows(self):
        rows = {}
        for row in self._gaps_data:
            key = (row['food_name'], row['gap_type'], row['gap_code'])
            if key not in rows:
                rows[key] = {col: row[col] for col in self.headers if col != 'number_occurrence'}
                rows[key]['number_occurrence'] = 1
            else:
                rows[key]['number_occurrence'] += 1

        for key, row in sorted(rows.items(), key=lambda item: item[0]):
            yield format_row([row[header] for header in self.headers])


class GapsDetailsData:
    title = 'Gaps By Item Details'
    slug = 'gaps_by_item_details'
    headers = [
        'gap_type', 'gap_code', 'gap_desc', 'food_code', 'food_name',
        'food_type', 'caseid', 'fao_who_gift_food_group_code',
        'fao_who_gift_food_group_description', 'user_food_group',
        'food_base_term', 'tag_1', 'other_tag_1', 'tag_2', 'other_tag_2',
        'tag_3', 'other_tag_3', 'tag_4', 'other_tag_4', 'tag_5', 'other_tag_5',
        'tag_6', 'other_tag_6', 'tag_7', 'other_tag_7', 'tag_8', 'other_tag_8',
        'tag_9', 'other_tag_9', 'tag_10', 'other_tag_10', 'conv_method_code',
        'conv_method_desc', 'conv_option_code', 'conv_option_desc',
        'measurement_amount', 'conv_units', 'portions',
        'nsr_conv_method_code_post_cooking', 'nsr_conv_method_desc_post_cooking',
        'nsr_conv_option_code_post_cooking', 'nsr_conv_option_desc_post_cooking',
        'nsr_measurement_amount_post_cooking', 'nsr_consumed_cooked_fraction',
        'conv_factor_used', 'conv_factor_food_code',
        'conv_factor_base_term_food_code', 'fct_data_used',
        'fct_food_code_exists', 'fct_base_term_food_code_exists',
        'fct_reference_food_code_exists', 'base_term_food_code',
        'reference_food_code', 'unique_respondent_id', 'recall_case_id',
        'opened_by_username', 'owner_name', 'visit_date'
    ]

    def __init__(self, gaps_data):
        self._gaps_data = gaps_data

    @property
    def rows(self):
        for row in sorted(self._gaps_data, key=lambda row: (row['food_name'], row['gap_type'], row['gap_code'])):
            yield format_row([row[header] for header in self.headers])
