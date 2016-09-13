from corehq.apps.userreports.models import DataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.sql.data_source import ConfigurableReportSqlDataSource
from corehq.apps.userreports.util import get_table_name


class ConfigurableReportDataSource(object):

    def __init__(self, domain, config_or_config_id, filters, aggregation_columns, columns, order_by):
        self.domain = domain
        self._data_source = None
        if isinstance(config_or_config_id, DataSourceConfiguration):
            self._config = config_or_config_id
            self._config_id = self._config._id
        else:
            assert isinstance(config_or_config_id, basestring)
            self._config = None
            self._config_id = config_or_config_id

        self._filters = filters
        self._order_by = order_by
        self._aggregation_columns = aggregation_columns
        self._columns = columns

    @property
    def data_source(self):
        if self._data_source is None:
            self._data_source = ConfigurableReportSqlDataSource(
                self.domain, self._config_id, self._filters,
                self._aggregation_columns, self._columns,
                self._order_by)
        return self._data_source

    @property
    def lang(self):
        return self.data_source.lang

    @lang.setter
    def lang(self, lang):
        self.data_source.lang = lang

    @property
    def aggregation_columns(self):
        return self.data_source.aggregation_columns

    @property
    def config(self):
        if self._config is None:
            self._config, _ = get_datasource_config(self._config_id, self.domain)
        return self._config

    @property
    def column_configs(self):
        return self.data_source.column_configs

    @property
    def filters(self):
        return self.data_source.filters

    def set_filter_values(self, filter_values):
        self.data_source.set_filter_values(filter_values)

    def defer_filters(self, filter_slugs):
        self.data_source.defer_filters(filter_slugs)

    def set_order_by(self, columns):
        self._order_by = columns

    @property
    def filter_values(self):
        return self.data_source.filter_values

    @property
    def group_by(self):
        return self.data_source.group_by

    @property
    def order_by(self):
        return self.data_source.order_by

    @property
    def columns(self):
        return self.data_source.columns

    @property
    def column_warnings(self):
        return self.data_source.column_warnings

    def get_data(self, start=None, limit=None):
        return self.data_source.get_data(start, limit)

    @property
    def has_total_row(self):
        return self.data_source.has_total_row

    def get_total_records(self):
        return self.data_source.get_total_records()

    def get_total_row(self):
        return self.data_source.get_total_row()
