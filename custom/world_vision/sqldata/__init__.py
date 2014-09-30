from sqlagg.columns import SimpleColumn
from sqlagg.filters import IN
from sqlagg.filters import EQ, BETWEEN, LTE
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn, DataFormatter, TableDataFormat, calculate_total_row


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
    custom_total_calculate = False

    def percent_fn(self, x, y):
        return "%.2f%%" % (100 * float(y or 0) / (x or 1))

    @property
    def filters(self):
        filters = None

        if 'startdate' in self.config and 'enddate' in self.config:
            filters = [BETWEEN("date", "startdate", "enddate")]
        elif 'startdate' not in self.config and 'enddate' not in self.config:
            filters =  []
        elif 'startdate' in self.config and 'enddate' not in self.config:
            filters = [BETWEEN("date", "startdate", "enddate")]
        elif 'startdate' not in self.config and 'enddate' in self.config:
            filters = [LTE("date", 'enddate')]

        if 'enddate' not in self.config and len(filters) > 1:
            self.config['enddate'] = self.config['today']
            self.config['stred'] = self.config['today']

        for k, v in LOCATION_HIERARCHY.iteritems():
            if v['prop'] in self.config and self.config[v['prop']]:
                filters.append(IN(k, v['prop']))
        return filters

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