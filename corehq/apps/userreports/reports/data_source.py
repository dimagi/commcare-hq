from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.userreports.const import UCR_ES_BACKEND, UCR_LABORATORY_BACKEND, UCR_SQL_BACKEND, UCR_ES_PRIMARY
from corehq.apps.userreports.models import DataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.custom.data_source import ConfigurableReportCustomDataSource
from corehq.apps.userreports.es.data_source import ConfigurableReportEsDataSource
from corehq.apps.userreports.sql.data_source import ConfigurableReportSqlDataSource
from corehq.apps.userreports.util import get_backend_id
import six


class ConfigurableReportDataSource(object):
    """
    This class is a proxy class for ConfigurableReportSqlDataSource
        and ConfigurableReportEsDataSource, which include logic to
        query the SQL or ES datasource table.
    """

    def __init__(self, domain, config_or_config_id, filters, aggregation_columns, columns, order_by,
                 backend=None, custom_query_provider=None):
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
            self._config = None
            self._config_id = config_or_config_id

        self._filters = filters
        self._order_by = order_by
        self._aggregation_columns = aggregation_columns
        self._columns = columns
        if backend:
            self.override_backend_id(backend)
        else:
            self._backend = None

        self._custom_query_provider = custom_query_provider

    @classmethod
    def from_spec(cls, spec, include_prefilters=False, backend=None):
        order_by = [(o['field'], o['order']) for o in spec.sort_expression]
        filters = spec.filters if include_prefilters else spec.filters_without_prefilters
        return cls(
            domain=spec.domain,
            config_or_config_id=spec.config_id,
            filters=filters,
            aggregation_columns=spec.aggregation_columns,
            columns=spec.report_columns,
            order_by=order_by,
            backend=backend,
            custom_query_provider=spec.custom_query_provider
        )

    @property
    def backend(self):
        if self._backend is None:
            self._backend = get_backend_id(self.config)
        return self._backend

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
            elif self.backend == UCR_ES_BACKEND:
                self._data_source = ConfigurableReportEsDataSource(
                    self.domain, self.config, self._filters,
                    self._aggregation_columns, self._columns,
                    self._order_by)
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
            self._config, _ = get_datasource_config(self._config_id, self.domain)
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
        return self.data_source.get_data(start, limit)

    @property
    def has_total_row(self):
        return self.data_source.has_total_row

    def get_total_records(self):
        return self.data_source.get_total_records()

    def get_total_row(self):
        return self.data_source.get_total_row()

    def override_backend_id(self, new_backend):
        assert get_backend_id(self.config, can_handle_laboratory=True) in (UCR_LABORATORY_BACKEND, UCR_ES_PRIMARY)
        assert new_backend == UCR_ES_BACKEND or new_backend == UCR_SQL_BACKEND
        self._backend = new_backend
        self.config.backend_id = new_backend
