from sqlagg.columns import SimpleColumn
from sqlagg.filters import GTE, LTE, EQ

from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports.sqlreport import DatabaseColumn
from custom.inddex.sqldata import FoodConsumptionDataSourceMixin


def get_slugs(slugs, config):
    filters = []
    for slug in slugs:
        if config.get(slug):
            filters.append(EQ(slug, slug))

    return filters


class ReportDataMixin(FoodConsumptionDataSourceMixin):
    title = None
    table_names = []
    headers_in_order = []
    TABLE_NAMES = [
        'doc_id', 'inserted_at', 'recall_case_id', 'owner_name', 'opened_by_username', 'recall_status',
        'unique_respondent_id', 'gender', 'age', 'supplements', 'urban_rural', 'pregnant', 'breastfeeding',
        'food_code', 'reference_food_code', 'food_type', 'include_in_analysis', 'food_status', 'recall_date',
        'opened_date', 'eating_time', 'time_block', 'already_reported_food', 'already_reported_food_caseid',
        'is_ingredient', 'ingr_recipe_case_id', 'ingr_recipe_code', 'short_name', 'food_name', 'recipe_name',
        'food_base_term', 'tag_1', 'other_tag_1', 'tag_2', 'other_tag_2', 'tag_3', 'other_tag_3', 'tag_4',
        'other_tag_4', 'tag_5', 'other_tag_5', 'tag_6', 'other_tag_6', 'tag_7', 'other_tag_7', 'tag_8',
        'other_tag_8', 'tag_9', 'other_tag_9', 'tag_10', 'other_tag_10', 'conv_method', 'conv_method_desc',
        'conv_option', 'conv_option_desc', 'conv_size', 'conv_units', 'quantity',
        'nsr_post_cooking_conv_method_code', 'nsr_post_cooking_conv_option_code',
        'nsr_post_cooking_conv_option_desc', 'nsr_post_cooking_conv_size', 'nsr_same_conv_method'
    ]
    OBLIGATORY_TABLE_NAMES = ['reference_food_code', 'conv_method', 'conv_option']
    OBLIGATORY_COUCH_NAMES = [
        'conv_factor_gap_code', 'fct_gap_code', 'conv_factor_reference_food_code',
        'fct_reference_food_code_exists', 'fao_who_gift_food_group_description', 'conv_factor_gap_desc',
        'fct_gap_desc', 'fct_used', 'report_data_type'
    ]

    @property
    def filters(self):
        filters = [GTE('recall_date', 'startdate'), LTE('recall_date', 'enddate')]
        if self.config['case_owners']:
            filters.append(EQ('owner_name', 'case_owners'))

        return filters

    @property
    def additional_filters(self):
        return {}

    @property
    def headers(self):
        return [DataTablesColumn(header) for header in self.headers_in_order]

    @property
    def columns(self):
        return [
            DatabaseColumn(header, SimpleColumn(header))
            for header in self.headers_in_order if header in self.TABLE_NAMES
        ]

    @property
    def not_ds_columns(self):
        return [
            DatabaseColumn(header, SimpleColumn(header))
            for header in self.headers_in_order
            if header not in set(self.TABLE_NAMES + self.OBLIGATORY_TABLE_NAMES)
        ]

    @property
    def group_by(self):
        return [
            header for header in self.headers_in_order
            if header in set(self.TABLE_NAMES + self.OBLIGATORY_TABLE_NAMES)
        ]

    @property
    def rows(self):
        return []

    @property
    def default_values(self):
        return {}


class GapsReportByItemDataMixin(ReportDataMixin):

    @property
    def filters(self):
        filters = super().filters
        filters += get_slugs(['food_type', 'recall_status'], self.config)

        return filters

    @property
    def additional_filters(self):
        return {
            'fct_gap_type': self.config['gap_type'],
            'conv_gap_type': self.config['gap_type'],
            'fao_who_gift_food_group_desc': self.config['fao_who_gift_food_group_description'],
            'fct_gap_desc': self.config['gap_description'],
            'conv_factor_gap_desc': self.config['gap_description'],
        }


class GapsReportSummaryDataMixin(ReportDataMixin):

    @property
    def filters(self):
        filters = super().filters
        filters += get_slugs([], self.config)

        return filters

    @property
    def additional_filters(self):
        return {
            'fct_gap_type': self.config['gap_type'],
            'conv_gap_type': self.config['gap_type'],
        }


class NutrientIntakesDataMixin(ReportDataMixin):

    @property
    def filters(self):
        filters = super().filters
        slugs = ['gender', 'pregnant', 'breastfeeding', 'urban_rural', 'supplements', 'recall_status']
        filters += get_slugs(slugs, self.config)

        return filters
