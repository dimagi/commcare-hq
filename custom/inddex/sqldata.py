from memoized import memoized
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

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], FOOD_CONSUMPTION)


class FiltersData(FoodConsumptionDataSourceMixin):

    @property
    def group_by(self):
        return ['owner_name']

    @property
    def headers(self):
        return [
            DataTablesColumn('Case owner'),
        ]

    @property
    def columns(self):
        return [
            DatabaseColumn('Case owner', SimpleColumn('owner_name')),
        ]

    @property
    @memoized
    def rows(self):
        case_owners = []
        for element in self.get_data():
            case_owner = element.get('owner_name')
            if case_owner and case_owner not in case_owners:
                case_owners.append(element['owner_name'])

        return case_owners,
