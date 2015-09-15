from collections import OrderedDict

from django.utils.translation import ugettext as _
from sqlagg import (
    ColumnNotFoundException,
    TableNotFoundException,
)
from sqlalchemy.exc import ProgrammingError

from corehq.apps.reports.sqlreport import SqlData
from corehq.apps.userreports.exceptions import (
    UserReportsError, TableNotFoundWarning,
    SortConfigurationError)
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.reports.sorting import get_default_sort_value
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
        self._column_configs = OrderedDict()
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
        if len(self.columns) > 50:
            raise UserReportsError(_("This report has too many columns to be displayed"))
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

        return self._sort_data(ret)

    def _sort_data(self, data):
        # TODO: Should sort in the database instead of memory, but not currently supported by sqlagg.
        try:
            # If a sort order is specified, sort by it.
            if self._order_by:
                for col in reversed(self._order_by):
                    sort_column_id, order = col
                    is_descending = order == DESCENDING
                    try:
                        matching_report_column = self._column_configs[sort_column_id]
                    except KeyError:
                        raise SortConfigurationError('Sort column {} not found in report!'.format(sort_column_id))

                    def get_datatype(report_column):
                        """
                        Given a report column, get the data type by trying to pull it out
                        from the data source config of the db column it points at. Defaults to "string"
                        """
                        try:
                            field = report_column.field
                        except AttributeError:
                            # if the report column doesn't have a field object, default to string.
                            # necessary for percent columns
                            return 'string'

                        matching_indicators = filter(
                            lambda configured_indicator: configured_indicator['column_id'] == field,
                            self.config.configured_indicators
                        )
                        if not len(matching_indicators) == 1:
                            raise SortConfigurationError(
                                'Number of indicators matching column %(col)s is %(num_matching)d' % {
                                    'col': col[0],
                                    'num_matching': len(matching_indicators),
                                }
                            )
                        return matching_indicators[0]['datatype']

                    datatype = get_datatype(matching_report_column)

                    def sort_by(row):
                        value = row.get(sort_column_id, None)
                        return value or get_default_sort_value(datatype)

                    data.sort(
                        key=sort_by,
                        reverse=is_descending
                    )
                return data
            # Otherwise sort by the first column
            else:
                return sorted(data, key=lambda x: x.get(
                    self.column_configs[0].column_id,
                    next(x.itervalues())
                ))
        except (SortConfigurationError, TypeError):
            # if the data isn't sortable according to the report spec
            # just return the data in the order we got it
            return data

    @property
    def has_total_row(self):
        return any(column_config.calculate_total for column_config in self.column_configs)

    def get_total_records(self):
        return len(self.get_data())
