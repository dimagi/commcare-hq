from sqlagg.columns import SimpleColumn
from sqlagg.filters import EQ, GTE, LTE

from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports.sqlreport import DatabaseColumn
from custom.inddex.couchdata import CouchData
from custom.inddex.sqldata import FoodConsumptionDataSourceMixin


class GapsReportByItemDataMixin(FoodConsumptionDataSourceMixin):
    total_row = None
    title = None
    slug = None
    couch_db = None
    _NAMES = {
        'ds': [
            'food_base_term', 'food_code', 'food_name', 'food_type', 'other_tag_1', 'other_tag_2', 'other_tag_3',
            'other_tag_4', 'other_tag_5', 'other_tag_6', 'other_tag_7', 'other_tag_8', 'other_tag_9',
            'other_tag_10', 'tag_1', 'tag_2', 'tag_3', 'tag_4', 'tag_5', 'tag_6', 'tag_7',
            'tag_8', 'tag_9', 'tag_10',
            # 'external_id'
        ],
        'not_ds': [
            'fao_who_gift_food_group_code', 'fao_who_gift_food_group_description', 'report_data_type'
        ]
    }

    @property
    def filters(self):
        filters = [GTE('opened_date', 'startdate'), LTE('opened_date', 'enddate')]
        for slug in ['food_code', 'food_type', 'recall_status']:
            if self.config[slug]:
                filters.append(EQ(slug, slug))

        return filters

    @property
    def headers(self):
        raw_headers = {
            'ds': self._NAMES['ds'] + self.additional_headers['ds'],
            'not_ds': self._NAMES['not_ds'] + self.additional_headers['not_ds']
        }

        return [DataTablesColumn(value) for key, values in raw_headers.items() for value in values]

    @property
    def additional_headers(self):
        return {'ds': [], 'not_ds': []}

    @property
    def columns(self):
        return [
            DatabaseColumn(self._normalize_text(x), SimpleColumn(x))
            for x in self._NAMES['ds'] + self.additional_columns
        ]

    @property
    def additional_columns(self):
        return ['doc_id', 'reference_food_code']

    @property
    def group_by(self):
        return [x for x in self._NAMES['ds'] + self.additional_columns]

    @property
    def raw_rows(self):
        return self.get_data()

    @staticmethod
    def _normalize_text(text):
        return text.replace('_', ' ', text.count('_')).capitalize()


class GapsReportByItemSummaryData(GapsReportByItemDataMixin):
    total_row = None
    title = 'Gaps Report By Item - Summary'
    slug = 'gaps_report_by_item_summary'

    def __init__(self, config):
        super(GapsReportByItemSummaryData, self).__init__()
        self.config = config
        self.couch_db = CouchData(domain=config['domain'], tables=('conv_factors', 'food_composition_table'))

    @property
    def additional_headers(self):
        return {
            'ds': [],
            'not_ds': [
                'number_of_occurrences', 'conv_factor_gap_code', 'conv_factor_gap_description',
                'fct_gap_code', 'fct_gap_desc', 'report_data_type',
            ]
        }

    @property
    def rows(self):
        raw_rows = super(GapsReportByItemSummaryData, self).raw_rows
        for row in raw_rows:
            for col in self.additional_columns:
                row.pop(col)

        return [x.values() for x in raw_rows]


class GapsReportByItemDetailsData(GapsReportByItemDataMixin):
    total_row = None
    title = 'Gaps Report By Item - Details'
    slug = 'gaps_report_by_item_details'
    ADDITIONAL_NAMES = [
        'conv_method', 'conv_method_desc', 'conv_option', 'conv_option_desc', 'conv_size', 'conv_units',
        'opened_by_username', 'owner_name', 'quantity', 'recall_date', 'short_name', 'time_block',
        'unique_respondent_id', 'recall_case_id'
    ]

    def __init__(self, config):
        super(GapsReportByItemDetailsData, self).__init__()
        self.config = config
        self.couch_db = CouchData(domain=config['domain'], tables=('conv_factors', 'food_composition_table'))

    @property
    def additional_headers(self):
        return {
            'ds': self.ADDITIONAL_NAMES,
            'not_ds': [
                'conv_factor_food_code', 'conv_factor_parent_food_code', 'conv_factor_used', 'fct_food_code_exists',
                'fct_parent_food_code_exists', 'fct_used', 'gap_code', 'gap_desc', 'gap_type',
                'nsr_consumed_cooked_ratio', 'nsr_conv_method_desc_post_cooking', 'nsr_conv_method_post_cooking',
                'nsr_conv_option_desc_post_cooking', 'nsr_conv_option_post_cooking', 'nsr_conv_size_post_cooking',
                'nsr_same_conv_method', 'time_of_day', 'user_food_group_description'
            ]
        }

    @property
    def additional_columns(self):
        return self.ADDITIONAL_NAMES + super(GapsReportByItemDetailsData, self).additional_columns

    @property
    def rows(self):
        raw_rows = super(GapsReportByItemDetailsData, self).raw_rows
        for row in raw_rows:
            for col in self.additional_columns:
                row.pop(col)

        return [x.values() for x in raw_rows]
