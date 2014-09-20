from corehq.apps.reports.sqlreport import SqlData
from corehq.apps.userreports.sql import get_table_name
from dimagi.utils.decorators.memoized import memoized


class ConfigurableReportDataSource(SqlData):

    def __init__(self, domain, table_id, filters, aggregation_columns, columns):
        self.table_name = get_table_name(domain, table_id)
        self._filters = {f.slug: f for f in filters}
        self._filter_values = {}
        self.aggregation_columns = aggregation_columns
        self.column_configs = columns

    @property
    def filters(self):
        return [fv.to_sql_filter() for _, fv in self._filter_values.items()]

    def set_filter_values(self, filter_values):
        for filter_slug, value in filter_values.items():
            self._filter_values[filter_slug] = self._filters[filter_slug].create_filter_value(value)

    @property
    def filter_values(self):
        return {k: v for _, fv in self._filter_values.items() for k, v in fv.to_sql_values().items()}

    @property
    def group_by(self):
        return self.aggregation_columns

    @property
    @memoized
    def columns(self):
        return [col.get_sql_column() for col in self.column_configs]

    @memoized
    def get_data(self, slugs=None):
        ret = super(ConfigurableReportDataSource, self).get_data(slugs)
        # arbitrarily sort by the first column in memory
        # todo: should get pushed to the database but not currently supported in sqlagg
        return sorted(ret, key=lambda x: x[self.column_configs[0].field])

    def get_total_records(self):
        return len(self.get_data())
