from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.userreports.const import UCR_SQL_BACKEND, DATA_SOURCE_TYPE_STANDARD
from corehq.apps.userreports.models import DataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.custom.data_source import ConfigurableReportCustomDataSource
from corehq.apps.userreports.sql.data_source import ConfigurableReportSqlDataSource
from corehq.util.datadog.utils import ucr_load_counter
from corehq.util.python_compatibility import soft_assert_type_text
import six


class ConfigurableReportDataSource(object):
    """
    This class is a proxy class for ConfigurableReportSqlDataSource
    which is leftover from an experiment to use elasticsearch
    """

    def __init__(self, domain, config_or_config_id, filters, aggregation_columns, columns, order_by,
                 custom_query_provider=None, data_source_type=DATA_SOURCE_TYPE_STANDARD):
        """
            config_or_config_id: an instance of DataSourceConfiguration or an id pointing to it
        """
        self.domain = domain
        self._data_source = None
        if isinstance(config_or_config_id, DataSourceConfiguration):
            self._config = config_or_config_id
            self._config_id = self._config._id
        else:
            assert isinstance(config_or_config_id, six.string_types)
            soft_assert_type_text(config_or_config_id)
            self._config = None
            self._config_id = config_or_config_id

        self.data_source_type = data_source_type
        self._filters = filters
        self._order_by = order_by
        self._aggregation_columns = aggregation_columns
        self._columns = columns

        self._custom_query_provider = custom_query_provider
        self._track_load = None

    @classmethod
    def from_spec(cls, spec, include_prefilters=False):
        order_by = [(o['field'], o['order']) for o in spec.sort_expression]
        filters = spec.filters if include_prefilters else spec.filters_without_prefilters
        return cls(
            domain=spec.domain,
            config_or_config_id=spec.config_id,
            data_source_type=spec.data_source_type,
            filters=filters,
            aggregation_columns=spec.aggregation_columns,
            columns=spec.report_columns,
            order_by=order_by,
            custom_query_provider=spec.custom_query_provider
        )

    def track_load(self, value):
        if not self._track_load:
            # make this lazy to avoid loading the config in __init__
            self._track_load = ucr_load_counter(self.config.engine_id, 'ucr_report', self.config.domain)
        self._track_load(value)

    @property
    def backend(self):
        return UCR_SQL_BACKEND

    @property
    def data_source(self):
        if self._data_source is None:
            if self._custom_query_provider:
                self._data_source = ConfigurableReportCustomDataSource(
                    self.domain, self.config, self._filters,
                    self._aggregation_columns, self._columns,
                    self._order_by
                )
                self._data_source.set_provider(self._custom_query_provider)
            else:
                self._data_source = ConfigurableReportSqlDataSource(
                    self.domain, self.config, self._filters,
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
    def config(self):
        if self._config is None:
            self._config, _ = get_datasource_config(self._config_id, self.domain, self.data_source_type)
        return self._config

    @property
    def top_level_columns(self):
        return self.data_source.top_level_columns

    def set_filter_values(self, filter_values):
        self.data_source.set_filter_values(filter_values)

    def set_defer_fields(self, defer_fields):
        self.data_source.set_defer_fields(defer_fields)

    def set_order_by(self, columns):
        self.data_source.set_order_by(columns)

    @property
    def group_by(self):
        return self.data_source.group_by

    @property
    def columns(self):
        return self.data_source.columns

    @property
    def inner_columns(self):
        return self.data_source.inner_columns

    @property
    def column_warnings(self):
        return self.data_source.column_warnings

    def get_data(self, start=None, limit=None):
        data = self.data_source.get_data(start, limit)
        self.track_load(len(data))
        return data

    @property
    def has_total_row(self):
        return self.data_source.has_total_row

    def get_total_records(self):
        return self.data_source.get_total_records()

    def get_total_row(self):
        return self.data_source.get_total_row()
