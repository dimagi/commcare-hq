from sqlagg.columns import SimpleColumn
from sqlagg.filters import AND, EQ, GTE, IN, LT, LTE, OR

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
    SPECIAL_COLS = [
        'age_range',
    ]
    MULTI_SELECT_COLS = [
        'owner_id',
        'urban_rural',
    ]
    SINGLE_SELECT_COLS = [
        'breastfeeding',
        'gender',
        'pregnant',
        'recall_status',
        'supplements'
    ]
    FILTERABLE_COLUMNS = (SPECIAL_COLS + MULTI_SELECT_COLS + SINGLE_SELECT_COLS)

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
        if self._age_ranges:
            filters.append(self._get_age_range_filter())
        for col in self.MULTI_SELECT_COLS:
            if self.config.get(col):
                infilter_bindparams = get_INFilter_bindparams(col, self.config[col])
                filters.append(IN(col, infilter_bindparams))
        for col in self.SINGLE_SELECT_COLS:
            if self.config.get(col):
                filters.append(EQ(col, col))
        return filters

    @property
    def _age_ranges(self):
        ranges = {age_range.slug: age_range for age_range in AGE_RANGES}
        return [ranges[slug] for slug in self.config.get('age_range', [])]

    def _get_age_range_filter(self):
        filters = [
            AND([GTE(age_range.column, age_range.lower_param),
                 LT(age_range.column, age_range.upper_param)])
            for age_range in self._age_ranges
        ]
        return filters[0] if len(filters) == 1 else OR(filters)

    def _get_age_range_filter_values(self):
        values = {}
        for age_range in self._age_ranges:
            values[age_range.lower_param] = age_range.lower_bound
            values[age_range.upper_param] = age_range.upper_bound
        return values

    @property
    def filter_values(self):
        filter_values = super().filter_values
        for key in self.SINGLE_SELECT_COLS:
            if filter_values.get(key):
                filter_values[key] = filter_values[key][0]
        for key in self.MULTI_SELECT_COLS:
            clean_IN_filter_value(filter_values, key)
        if self._age_ranges:
            filter_values.update(self._get_age_range_filter_values())
        return filter_values
