from sqlagg.columns import SimpleColumn
from sqlagg.filters import AND, EQ, GTE, IN, LT, LTE

from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData
from corehq.apps.reports.util import get_INFilter_bindparams
from corehq.apps.userreports.util import get_table_name
from corehq.sql_db.connections import UCR_ENGINE_ID
from custom.utils.utils import clean_IN_filter_value

from .const import AGE_RANGES, FOOD_CONSUMPTION


class FoodCaseData(SqlData):
    """This class pulls raw data from the food_consumption_indicators UCR"""
    group_by = ['doc_id']
    engine_id = UCR_ENGINE_ID
    FILTERABLE_COLUMNS = [
        'age_range',
        'breastfeeding',
        'gender',
        'owner_id',
        'pregnant',
        'recall_status',
        'supplements'
        'urban_rural',
    ]

    @property
    def columns(self):
        from .food import INDICATORS
        column_ids = ['doc_id', 'inserted_at'] + [i.slug for i in INDICATORS if i.in_ucr]
        return [DatabaseColumn(col_id, SimpleColumn(col_id)) for col_id in column_ids]

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], FOOD_CONSUMPTION)

    @property
    def filters(self):
        filters = [GTE('visit_date', 'startdate'), LTE('visit_date', 'enddate')]
        if self._age_range:
            filters.append(self._get_age_range_filter())
        for multiselect_column in ['owner_id', 'urban_rural']:
            if self.config.get(multiselect_column):
                infilter_bindparams = get_INFilter_bindparams(multiselect_column,
                                                              self.config[multiselect_column])
                filters.append(IN(multiselect_column, infilter_bindparams))
        for column in [
                'breastfeeding',
                'gender',
                'pregnant',
                'recall_status',
                'supplements'
                'urban_rural',
        ]:
            if self.config.get(column):
                filters.append(EQ(column, column))
        return filters

    @property
    def _age_range(self):
        if self.config.get('age_range'):
            return {age_range.slug: age_range for age_range in AGE_RANGES}[self.config['age_range']]

    def _get_age_range_filter(self):
        return AND([GTE(self._age_range.column, 'age_range_lower_bound'),
                    LT(self._age_range.column, 'age_range_upper_bound')])

    def _get_age_range_filter_values(self):
        return {
            'age_range_lower_bound': self._age_range.lower_bound,
            'age_range_upper_bound': self._age_range.upper_bound,
        }

    @property
    def filter_values(self):
        filter_values = super().filter_values
        for key in ['owner_id', 'urban_rural']:
            clean_IN_filter_value(filter_values, key)
        if self._age_range:
            filter_values.update(self._get_age_range_filter_values())
        return filter_values
