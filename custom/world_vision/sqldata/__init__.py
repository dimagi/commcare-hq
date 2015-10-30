from sqlagg.columns import SimpleColumn
from sqlagg.filters import IN, AND, GTE, OR
from sqlagg.filters import EQ, BETWEEN, LTE
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn, DataFormatter, TableDataFormat, calculate_total_row
from corehq.apps.reports.util import get_INFilter_bindparams
from custom.utils.utils import clean_IN_filter_value

LOCATION_HIERARCHY = {
    "lvl_1": {
        "prop": "lvl_1",
        "name": "State"
    },
    "lvl_2": {
        "prop": "lvl_2",
        "name": "District"
    },
    "lvl_3": {
        "prop": "lvl_3",
        "name": "Block"
    },
    "lvl_4": {
        "prop": "lvl_4",
        "name": "PHC"
    }
}


class BaseSqlData(SqlData):
    show_total = False
    datatables = False
    show_charts = False
    no_value = {'sort_key': 0, 'html': 0}
    fix_left_col = False
    total_row_name = "Total"
    chart_title = ''
    custom_total_calculate = False
    accordion_start = True
    accordion_end = True
    chart_only = False
    table_only = False

    def percent_fn(self, x, y):
        return "%.0f%%" % (100 * float(y or 0) / (x or 1))

    def get_tooltip(self, mapping, key):
        return mapping.get(key, '')

    @property
    def filters(self):
        filters = None
        if 'enddate' not in self.config:
            self.config['enddate'] = self.config['today']
            self.config['stred'] = self.config['today']

        if 'startdate' in self.config:
            filters = [AND([LTE("date", "enddate"), OR([GTE('closed_on', "startdate"), EQ('closed_on', 'empty')])])]
        else:
            self.config['strsd'] = '0001-01-01'
            filters = [LTE("date", "enddate")]

        for k, v in LOCATION_HIERARCHY.iteritems():
            if v['prop'] in self.config and self.config[v['prop']]:
                filters.append(IN(k, get_INFilter_bindparams(k, self.config[v['prop']])))
        return filters

    @property
    def filter_values(self):
        filter_values = super(BaseSqlData, self).filter_values

        for k, v in LOCATION_HIERARCHY.iteritems():
            clean_IN_filter_value(filter_values, v['prop'])

        return filter_values

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Entity'), DataTablesColumn('Number'), DataTablesColumn('Percentage')])

    @property
    def group_by(self):
        return []

    @property
    def rows(self):
        formatter = DataFormatter(TableDataFormat(self.columns, no_value=self.no_value))
        return list(formatter.format(self.data, keys=self.keys, group_by=self.group_by))

    @property
    def data(self):
        return super(BaseSqlData, self).data

    def _get_rows(self, dict, rows):
        total_row = calculate_total_row(rows)
        total = total_row[-1] if total_row else 0
        result = []
        for (k, v) in dict.iteritems():
            number = [row[1]['html'] for row in rows if row[0] == k]
            number = number[0] if number else 0
            result.append([{'sort_key':v, 'html': v}, {'sort_key':number, 'html': number},
                   {'sort_key':self.percent_fn(total, number), 'html': self.percent_fn(total, number)}
            ])
        return result

class LocationSqlData(SqlData):
    table_name = "fluff_WorldVisionHierarchyFluff"
    geography_config = LOCATION_HIERARCHY

    @property
    def filters(self):
        return [EQ('domain', 'domain'), "lvl_1 != ''", "lvl_2 != ''", "lvl_3 != ''", "lvl_4 != ''"]

    @property
    def filter_values(self):
        return {'domain': 'wvindia2'}

    @property
    def group_by(self):
        return [k for k in self.geography_config.keys()]

    @property
    def columns(self):
        levels = [k for k in self.geography_config.keys()]
        columns = []
        for k in levels:
            columns.append(DatabaseColumn(k, SimpleColumn(k)))
        return columns
