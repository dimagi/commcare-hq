import datetime
from datetime import date
from django.utils.datastructures import SortedDict
from sqlagg import (
    ColumnNotFoundException,
    TableNotFoundException,
)
from sqlalchemy.exc import ProgrammingError
from corehq.apps.reports.sqlreport import SqlData
from corehq.apps.userreports.exceptions import (
    UserReportsError, TableNotFoundWarning,
)
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.reports.specs import DESCENDING
from corehq.apps.userreports.sql import get_table_name
from corehq.apps.userreports.sql.connection import get_engine_id
from corehq.apps.userreports.views import get_datasource_config_or_404
from dimagi.utils.decorators.memoized import memoized


class ConfigurableReportDataSource(SqlData):

    def __init__(self, domain, config_or_config_id, filters, aggregation_columns, columns):
        self.lang = None
        self.domain = domain
        if isinstance(config_or_config_id, DataSourceConfiguration):
            self._config = config_or_config_id
            self._config_id = self._config._id
        else:
            assert isinstance(config_or_config_id, basestring)
            self._config = None
            self._config_id = config_or_config_id

        self._filters = {f.slug: f for f in filters}
        self._filter_values = {}
        self._order_by = []
        self.aggregation_columns = aggregation_columns
        self._column_configs = SortedDict()
        for column in columns:
            # should be caught in validation prior to reaching this
            assert column.column_id not in self._column_configs, \
                'Report {} in domain {} has more than one {} column defined!'.format(
                    self._config_id, self.domain, column.column_id,
                )
            self._column_configs[column.column_id] = column

    @property
    def config(self):
        if self._config is None:
            self._config, _ = get_datasource_config_or_404(self._config_id, self.domain)
        return self._config

    @property
    def engine_id(self):
        return get_engine_id(self.config)

    @property
    def column_configs(self):
        return self._column_configs.values()

    @property
    def table_name(self):
        return get_table_name(self.domain, self.config.table_id)

    @property
    def filters(self):
        return [fv.to_sql_filter() for fv in self._filter_values.values()]

    def set_filter_values(self, filter_values):
        for filter_slug, value in filter_values.items():
            self._filter_values[filter_slug] = self._filters[filter_slug].create_filter_value(value)

    def set_order_by(self, columns):
        self._order_by = columns

    @property
    def filter_values(self):
        return {k: v for fv in self._filter_values.values() for k, v in fv.to_sql_values().items()}

    @property
    def group_by(self):
        def _contributions(column_id):
            # ask each column for its group_by contribution and combine to a single list
            # if the column isn't found just treat it as a normal field
            if column_id in self._column_configs:
                return self._column_configs[col_id].get_group_by_columns()
            else:
                return [column_id]

        return [
            group_by for col_id in self.aggregation_columns
            for group_by in _contributions(col_id)
        ]

    @property
    def columns(self):
        return [c for sql_conf in self.sql_column_configs for c in sql_conf.columns]

    @property
    def sql_column_configs(self):
        return [col.get_sql_column_config(self.config, self.lang) for col in self.column_configs]

    @property
    def column_warnings(self):
        return [w for sql_conf in self.sql_column_configs for w in sql_conf.warnings]

    @memoized
    def get_data(self, slugs=None):
        try:
            ret = super(ConfigurableReportDataSource, self).get_data(slugs)
            for report_column in self.column_configs:
                report_column.format_data(ret)
        except (
            ColumnNotFoundException,
            ProgrammingError,
        ) as e:
            raise UserReportsError(e.message)
        except TableNotFoundException as e:
            raise TableNotFoundWarning
        # TODO: Should sort in the database instead of memory, but not currently supported by sqlagg.
        try:
            # If a sort order is specified, sort by it.
            if self._order_by:
                for col in reversed(self._order_by):
                    is_descending = col[1] == DESCENDING
                    is_date = any(
                        configured_indicator['datatype'] == 'date'
                        for configured_indicator in self.config.configured_indicators
                        if configured_indicator['column_id'] == col[0]
                    )
                    default_sort_by_date = (
                        date(datetime.MINYEAR, 1, 1)
                        if is_descending else date(datetime.MAXYEAR, 12, 31)
                    )
                    value = lambda x: x.get(col[0], None)
                    sort_by_value = lambda x: (
                        value(x)
                        or (default_sort_by_date if is_date else value(x))
                    )
                    ret.sort(
                        key=sort_by_value,
                        reverse=is_descending
                    )
                return ret
            # Otherwise sort by the first column
            else:
                return sorted(ret, key=lambda x: x.get(
                    self.column_configs[0].column_id,
                    next(x.itervalues())
                ))
        except TypeError:
            # if the first column isn't sortable just return the data in the order we got it
            return ret

    def get_total_records(self):
        return len(self.get_data())
