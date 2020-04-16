from sqlagg.columns import SimpleColumn
from sqlagg.filters import EQ, GTE, LT, LTE

from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData
from corehq.apps.userreports.util import get_table_name
from corehq.sql_db.connections import UCR_ENGINE_ID

from .const import FOOD_CONSUMPTION, AGE_RANGES


class FoodCaseData(SqlData):
    """This class pulls raw data from the food_consumption_indicators UCR"""
    group_by = ['doc_id']
    engine_id = UCR_ENGINE_ID
    FILTERABLE_COLUMNS = [  # columns easily filtered by exact match
        'breastfeeding',
        'gender',
        'owner_name',
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
        filters = [GTE('recalled_date', 'startdate'), LTE('recalled_date', 'enddate')]
        for column in self.FILTERABLE_COLUMNS:
            if self.config.get(column):
                if column == 'age_range':
                    filters.append(self._age_range_filter)
                else:
                    filters.append(EQ(column, column))
        return filters

    @property
    def _age_range_filter(self):
        age_range = {age_range.slug: age_range for age_range in AGE_RANGES}[self.config['age_range']]
        return [GTE(age_range.column, age_range.lower_bound),
                LT(age_range.column, age_range.upper_bound)]
