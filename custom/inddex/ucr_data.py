from sqlagg.columns import SimpleColumn
from sqlagg.filters import EQ, GTE, LTE

from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData
from corehq.apps.userreports.util import get_table_name

from .const import FOOD_CONSUMPTION
from .food import INDICATORS


class FoodCaseData(SqlData):
    """This class pulls raw data from the food_consumption_indicators UCR"""

    group_by = ['doc_id']

    @property
    def columns(self):
        column_ids = ['doc_id', 'inserted_at'] + [i.slug for i in INDICATORS if i.in_ucr]
        return [DatabaseColumn(col_id, SimpleColumn(col_id)) for col_id in column_ids]

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
