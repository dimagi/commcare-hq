from sqlagg.filters import BETWEEN
from corehq.apps.reports.sqlreport import SqlData, DataFormatter, TableDataFormat


class BaseSqlData(SqlData):
    datatables = False
    show_charts = False
    show_total = True
    custom_total_calculate = False
    no_value = {'sort_key': 0, 'html': 0}
    fix_left_col = False

    @property
    def filters(self):
        filters = [BETWEEN("date", "startdate", "enddate")]
        return filters

    @property
    def group_by(self):
        return []

    @property
    def rows(self):
        formatter = DataFormatter(TableDataFormat(self.columns, no_value=self.no_value))
        return list(formatter.format(self.data, keys=self.keys, group_by=self.group_by))
