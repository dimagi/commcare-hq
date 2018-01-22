from __future__ import absolute_import
from collections import OrderedDict

from corehq.apps.userreports.models import DataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.reports.specs import ReportColumn, ExpressionColumn
from corehq.apps.userreports.util import get_table_name
import six


class ConfigurableReportDataSourceMixin(object):
    def __init__(self, domain, config_or_config_id, filters, aggregation_columns, columns, order_by):
        self.lang = None
        self.domain = domain
        if isinstance(config_or_config_id, DataSourceConfiguration):
            self._config = config_or_config_id
            self._config_id = self._config._id
        else:
            assert isinstance(config_or_config_id, six.string_types)
            self._config = None
            self._config_id = config_or_config_id

        self._filters = {f.slug: f for f in filters}
        self._filter_values = {}
        self._dynamic_aggregation_columns = None
        self._deferred_filters = {}
        self._order_by = order_by
        self._aggregation_columns = aggregation_columns
        self._column_configs = OrderedDict()
        for column in columns:
            # should be caught in validation prior to reaching this
            assert column.column_id not in self._column_configs, \
                'Report {} in domain {} has more than one {} column defined!'.format(
                    self._config_id, self.domain, column.column_id,
                )
            self._column_configs[column.column_id] = column

    @property
    def aggregation_columns(self):
        return self._aggregation_columns + [
            deferred_filter.field for deferred_filter in self._deferred_filters.values()
            if deferred_filter.field not in self._aggregation_columns]

    @property
    def config(self):
        if self._config is None:
            self._config, _ = get_datasource_config(self._config_id, self.domain)
        return self._config

    @property
    def top_level_columns(self):
        """
        This returns a list of BaseReportColumn objects that define the top-level columns
        in the report. These top-level columns may resolve to more than one column in the
        underlying query or report (e.g. percentage columns or expanded columns)
        """
        return list(self._column_configs.values())

    @property
    def inner_columns(self):
        """
        This returns a list of Column objects that are contained within the top_level_columns
        above.
        """
        return [
            inner_col for col in self.top_level_columns
            for inner_col in col.get_column_config(self.config, self.lang).columns
        ]

    @property
    def top_level_db_columns(self):
        return [col for col in self.top_level_columns if isinstance(col, ReportColumn)]

    @property
    def top_level_computed_columns(self):
        return [col for col in self.top_level_columns if isinstance(col, ExpressionColumn)]

    @property
    def table_name(self):
        return get_table_name(self.domain, self.config.table_id)

    def set_filter_values(self, filter_values):
        for filter_slug, value in filter_values.items():
            self._filter_values[filter_slug] = self._filters[filter_slug].create_filter_value(value)

    def defer_filters(self, filter_slugs):
        self._deferred_filters.update({
            filter_slug: self._filters[filter_slug] for filter_slug in filter_slugs})

    def set_order_by(self, columns):
        self._order_by = columns

    @property
    def column_configs(self):
        return [col.get_column_config(self.config, self.lang) for col in self.top_level_db_columns]

    @property
    def column_warnings(self):
        return [w for conf in self.column_configs for w in conf.warnings]

    @property
    def has_total_row(self):
        return any(column_config.calculate_total for column_config in self.top_level_db_columns)

    def set_dynamic_aggregation_columns(self, columns):
        self._dynamic_aggregation_columns = columns

    @property
    def group_by(self):
        # ask each column for its group_by contribution and combine to a single list
        if self._dynamic_aggregation_columns:
            aggregation_columns = self._dynamic_aggregation_columns
        else:
            aggregation_columns = self.aggregation_columns
        return [
            group_by for col_id in aggregation_columns
            for group_by in self.get_db_column_ids(col_id)
        ]

    def get_db_column_ids(self, column_id):
        # for columns that end up being complex queries (e.g. aggregate dates)
        # there could be more than one column ID and they may specify aliases
        if column_id in self._column_configs:
            return self._column_configs[column_id].get_query_column_ids()
        else:
            # if the column isn't found just treat it as a normal field
            return [column_id]
