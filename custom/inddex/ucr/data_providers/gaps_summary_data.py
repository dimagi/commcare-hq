from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.sqlreport import DatabaseColumn
from sqlagg.columns import SimpleColumn
from sqlagg.filters import EQ

from custom.inddex.sqldata import FoodConsumptionDataSourceMixin


class GapsSummaryMasterOutputData(FoodConsumptionDataSourceMixin):
    title = 'Master Output'
    slug = 'master_output'

    def __init__(self, config, filters_config):
        self.config = config
        self.filters_config = filters_config

    @property
    def columns(self):
        return [
            DatabaseColumn('unique_respondent_id', SimpleColumn('unique_respondent_id')),
            DatabaseColumn('recall_case_id', SimpleColumn('recall_case_id')),
            DatabaseColumn('opened_date', SimpleColumn('opened_date')),
            DatabaseColumn('opened_by_username', SimpleColumn('opened_by_username')),
            DatabaseColumn('owner_name', SimpleColumn('owner_name')),
            DatabaseColumn('recall_date', SimpleColumn('recall_date')),
            DatabaseColumn('recall_status', SimpleColumn('recall_status')),
            DatabaseColumn('gender', SimpleColumn('gender')),
            DatabaseColumn('age', SimpleColumn('age')),
            DatabaseColumn('supplements', SimpleColumn('supplements')),
            DatabaseColumn('urban_rural', SimpleColumn('urban_rural')),
            DatabaseColumn('pregnant', SimpleColumn('pregnant')),
            DatabaseColumn('breastfeeding', SimpleColumn('breastfeeding')),
            DatabaseColumn('food_code', SimpleColumn('food_code')),
            DatabaseColumn('reference_food_code', SimpleColumn('reference_food_code')),
            DatabaseColumn('doc_id', SimpleColumn('doc_id')),
            DatabaseColumn('food_type', SimpleColumn('food_type')),
            DatabaseColumn('include_in_analysis', SimpleColumn('include_in_analysis')),
            DatabaseColumn('food_status', SimpleColumn('food_status')),
            DatabaseColumn('eating_time', SimpleColumn('eating_time')),
            DatabaseColumn('time_block', SimpleColumn('time_block')),
            DatabaseColumn('already_reported_food', SimpleColumn('already_reported_food')),
            DatabaseColumn('already_reported_food_caseid', SimpleColumn('already_reported_food_caseid')),
            DatabaseColumn('is_ingredient', SimpleColumn('is_ingredient')),
            DatabaseColumn('ingr_recipe_case_id', SimpleColumn('ingr_recipe_case_id')),
            DatabaseColumn('ingr_recipe_code', SimpleColumn('ingr_recipe_code')),
            DatabaseColumn('short_name', SimpleColumn('short_name')),
            DatabaseColumn('food_name', SimpleColumn('food_name')),
            DatabaseColumn('recipe_name', SimpleColumn('recipe_name')),
            DatabaseColumn('food_base_term', SimpleColumn('food_base_term')),
            DatabaseColumn('tag_1', SimpleColumn('tag_1')),
            DatabaseColumn('other_tag_1', SimpleColumn('other_tag_1')),
            DatabaseColumn('tag_2', SimpleColumn('tag_2')),
            DatabaseColumn('other_tag_2', SimpleColumn('other_tag_2')),
            DatabaseColumn('tag_3', SimpleColumn('tag_3')),
            DatabaseColumn('other_tag_3', SimpleColumn('other_tag_3')),
            DatabaseColumn('tag_4', SimpleColumn('tag_4')),
            DatabaseColumn('other_tag_4', SimpleColumn('other_tag_4')),
            DatabaseColumn('tag_5', SimpleColumn('tag_5')),
            DatabaseColumn('other_tag_5', SimpleColumn('other_tag_5')),
            DatabaseColumn('tag_6', SimpleColumn('tag_6')),
            DatabaseColumn('other_tag_6', SimpleColumn('other_tag_6')),
            DatabaseColumn('tag_7', SimpleColumn('tag_7')),
            DatabaseColumn('other_tag_7', SimpleColumn('other_tag_7')),
            DatabaseColumn('tag_8', SimpleColumn('tag_8')),
            DatabaseColumn('other_tag_8', SimpleColumn('other_tag_8')),
            DatabaseColumn('tag_9', SimpleColumn('tag_9')),
            DatabaseColumn('other_tag_9', SimpleColumn('other_tag_9')),
            DatabaseColumn('tag_10', SimpleColumn('tag_10')),
            DatabaseColumn('other_tag_10', SimpleColumn('other_tag_10')),
            DatabaseColumn('conv_method', SimpleColumn('conv_method')),
            DatabaseColumn('conv_method_desc', SimpleColumn('conv_method_desc')),
            DatabaseColumn('conv_option', SimpleColumn('conv_option')),
            DatabaseColumn('conv_option_desc', SimpleColumn('conv_option_desc')),
            DatabaseColumn('conv_size', SimpleColumn('conv_size')),
            DatabaseColumn('conv_units', SimpleColumn('conv_units')),
            DatabaseColumn('quantity', SimpleColumn('quantity'))
        ]

    @property
    def group_by(self):
        return ['unique_respondent_id', 'recall_case_id', 'opened_date', 'opened_by_username', 'owner_name',
                'recall_date', 'recall_status', 'gender', 'age', 'supplements',  'urban_rural', 'pregnant',
                'breastfeeding', 'food_code', 'reference_food_code', 'doc_id', 'food_type', 'include_in_analysis',
                'food_status', 'eating_time', 'time_block', 'already_reported_food', 'already_reported_food_caseid',
                'is_ingredient', 'ingr_recipe_case_id', 'ingr_recipe_code', 'short_name', 'food_name',
                'recipe_name', 'food_base_term', 'tag_1', 'other_tag_1', 'tag_2', 'other_tag_2', 'tag_3',
                'other_tag_3', 'tag_4', 'other_tag_4', 'tag_5', 'other_tag_5', 'tag_6', 'other_tag_6',
                'tag_7', 'other_tag_7', 'tag_8', 'other_tag_8', 'tag_9', 'other_tag_9', 'tag_10', 'other_tag_10',
                'conv_method', 'conv_method_desc', 'conv_option', 'conv_option_desc', 'conv_size', 'conv_units',
                'quantity']

    @property
    def headers(self):
        group_columns = tuple(self.group_by)
        headers = []
        for col in group_columns:
            headers.append(DataTablesColumn(col))
        return headers

    @property
    def filters(self):
        filters = []
        if self.filters_config['recall_status']:
            filters.append(EQ('recall_status', 'recall_status'))
        return filters

    @property
    def filter_values(self):
        return self.filters_config

    @property
    def rows(self):
        result = []
        data_rows = self.get_data()
        group_columns = tuple(self.group_by)

        for row in data_rows:
            result.append([row[x] for x in group_columns])
        return result


class ConvFactorGapsSummaryData(FoodConsumptionDataSourceMixin):
    title = 'Conv Factor Gaps Summary by Food Type'
    slug = 'conv_factor_gaps_summary_by_food_type'

    def __init__(self, config, filters_config):
        self.config = config
        self.filters_config = filters_config

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('conv_factor_gap_code'),
            DataTablesColumn('conv_factor_gap_desc'),
            DataTablesColumn('food_type'),
            DataTablesColumn('conv_gap_food_type_total'),
        )

    @property
    def filters(self):
        filters = []
        if self.filters_config['recall_status']:
            filters.append(EQ('recall_status', 'recall_status'))
        return filters

    @property
    def filter_values(self):
        return self.filters_config

    @property
    def rows(self):
        # TODO: add proper calculations instead
        # It's worth to ensure that elements are of type DataTablesColumn instead of string
        return [
                    [1,	'conv factor available', 'food_item', 600],
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
                    [9, 'not applicable', 'food_item', 400],
                    [9, 'not applicable', 'non_std_food', 0],
                    [9, 'not applicable', 'std_recipe', 25],
                    [9, 'not applicable', 'non_std_recipe', 0]
            ]


class FCTGapsSummaryData(FoodConsumptionDataSourceMixin):
    title = 'FCT Gaps Summary by Food Type'
    slug = 'fct_gaps_summary_by_food_type'

    def __init__(self, config, filters_config):
        self.config = config
        self.filters_config = filters_config

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('fct_gap_code'),
            DataTablesColumn('fct_gap_desc'),
            DataTablesColumn('food_type'),
            DataTablesColumn('fct_gap_food_type_total'),
        )

    @property
    def filters(self):
        filters = []
        if self.filters_config['recall_status']:
            filters.append(EQ('recall_status', 'recall_status'))
        return filters

    @property
    def filter_values(self):
        return self.filters_config

    @property
    def rows(self):
        # TODO: add proper calculations instead
        # It's worth to ensure that elements are of type DataTablesColumn instead of string
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
                    [4, 'ingredient(s) using fct data from base term food code', 'std_recipe', 0],
                    [4, 'ingredient(s) using fct data from base term food code', 'non_std_recipe', 36],
                    [5, 'ingredient(s) using reference food code', 'food_item', 0],
                    [5, 'ingredient(s) using reference food code', 'non_std_food', 0],
                    [5, 'ingredient(s) using reference food code', 'std_recipe', 51],
                    [5, 'ingredient(s) using reference food code', 'non_std_recipe', 30],
                    [6, 'ingredient(s) not in fct', 'food_item', 0],
                    [6, 'ingredient(s) not in fct', 'non_std_food', 0],
                    [6, 'ingredient(s) not in fct', 'std_recipe', 0],
                    [6, 'ingredient(s) not in fct', 'non_std_recipe', 44],
                    [8, 'no fct data available', 'food_item', 0],
                    [8, 'no fct data available', 'non_std_food', 50],
                    [8, 'no fct data available', 'std_recipe', 0],
                    [8, 'no fct data available', 'non_std_recipe', 65],
                    [9, 'not applicable', 'food_item', 0],
                    [9, 'not applicable', 'non_std_food', 0],
                    [9, 'not applicable', 'std_recipe', 50],
                    [9, 'not applicable', 'non_std_recipe', 0],
            ]
