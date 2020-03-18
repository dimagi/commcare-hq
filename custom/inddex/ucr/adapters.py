from sqlagg.columns import SimpleColumn
from sqlagg.filters import EQ, GTE, LTE

from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData
from corehq.apps.userreports.util import get_table_name
from custom.inddex.const import FOOD_CONSUMPTION


class FoodCaseData(SqlData):
    """This class pulls raw data from the food_consumption_indicators UCR"""

    group_by = ['doc_id']
    UCR_COLUMN_IDS = [
        'doc_id', 'inserted_at', 'recall_case_id', 'owner_name', 'opened_by_username', 'recall_status',
        'unique_respondent_id', 'gender', 'age_months_calculated', 'supplements', 'urban_rural', 'pregnant', 'breastfeeding',
        'food_code', 'reference_food_code', 'food_type', 'include_in_analysis', 'food_status', 'recalled_date',
        'opened_date', 'eating_time', 'time_block', 'already_reported_food', 'already_reported_food_case_id',
        'is_ingredient', 'ingr_recipe_case_id', 'ingr_recipe_code', 'short_name', 'food_name', 'recipe_name',
        'food_base_term', 'tag_1', 'other_tag_1', 'tag_2', 'other_tag_2', 'tag_3', 'other_tag_3', 'tag_4',
        'other_tag_4', 'tag_5', 'other_tag_5', 'tag_6', 'other_tag_6', 'tag_7', 'other_tag_7', 'tag_8',
        'other_tag_8', 'tag_9', 'other_tag_9', 'tag_10', 'other_tag_10', 'conv_method_code', 'conv_method_desc',
        'conv_option_code', 'conv_option_desc', 'measurement_amount', 'conv_units', 'portions',
        'nsr_conv_method_code_post_cooking', 'nsr_conv_option_code_post_cooking',
        'nsr_conv_option_desc_post_cooking', 'nsr_measurement_amount_post_cooking', 'nsr_same_conv_method',
        'respondent_id', 'recipe_case_id'
    ]
    columns = [DatabaseColumn(col_id, SimpleColumn(col_id)) for col_id in UCR_COLUMN_IDS]

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], FOOD_CONSUMPTION)

    @property
    def filters(self):
        filters = [GTE('recalled_date', 'startdate'), LTE('recalled_date', 'enddate')]
        if self.config['case_owners']:
            filters.append(EQ('owner_name', 'case_owners'))
        if self.config['recall_status']:
            filters.append(EQ('recall_status', 'recall_status'))
        return filters
