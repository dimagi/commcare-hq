from sqlagg.columns import SimpleColumn

from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from corehq.apps.userreports.util import get_table_name

FOOD_CONSUMPTION = 'food_consumption_indicators'


class DataSourceMixin(SqlData):

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def filters(self):
        return []

    @property
    def group_by(self):
        return []

    @property
    def columns(self):
        return []


class FoodConsumptionDataSourceMixin(DataSourceMixin):
    total_row = None
    filters_config = None

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], FOOD_CONSUMPTION)


class FoodCodeDataSource(FoodConsumptionDataSourceMixin):

    @property
    def group_by(self):
        return ['food_code']

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn('Food code'))

    @property
    def columns(self):
        return [
            DatabaseColumn('Food code', SimpleColumn('food_code')),
        ]


class FoodCodeData(FoodCodeDataSource):
    slug = 'food_code'
    comment = 'Food codes'
    title = 'Food code'
    show_total = False

    @property
    def rows(self):
        food_codes = [int(x['food_code']) for x in self.get_data() if x['food_code'] is not None]

        return sorted(set(food_codes))


class FoodBaseTermDataSource(FoodConsumptionDataSourceMixin):

    @property
    def group_by(self):
        return ['food_base_term']

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn('Food base term'))

    @property
    def columns(self):
        return [
            DatabaseColumn('Food base term', SimpleColumn('food_base_term')),
        ]


class FoodBaseTermData(FoodBaseTermDataSource):
    slug = 'food_base_term'
    comment = 'Food base terms'
    title = 'Food base term'
    show_total = False

    @property
    def rows(self):
        food_base_terms = [x['food_base_term'] for x in self.get_data() if x['food_base_term'] is not None]

        return sorted(set(food_base_terms))
