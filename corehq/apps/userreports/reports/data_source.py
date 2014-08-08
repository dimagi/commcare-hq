import random
from corehq.apps.reports.sqlreport import SqlData
from corehq.apps.userreports.sql import get_table_name
from dimagi.utils.decorators.memoized import memoized


class ConfigurableReportDataSource(SqlData):

    def __init__(self, domain, table_id, aggregation_columns, columns):
        self.table_name = get_table_name(domain, table_id)
        self.aggregation_columns = aggregation_columns
        self.column_configs = columns

    @property
    def filters(self):
        # todo: figure out how to wire these in
        return []

    @property
    def group_by(self):
        return self.aggregation_columns

    @property
    @memoized
    def columns(self):
        return [col.get_sql_column() for col in self.column_configs]

    @memoized
    def get_data(self, slugs=None):
        return super(ConfigurableReportDataSource, self).get_data(slugs)

    def get_total_records(self):
        return len(self.get_data())
