from __future__ import absolute_import
from __future__ import unicode_literals

from django.utils.decorators import method_decorator
from memoized import memoized

from corehq.apps.reports.api import ReportDataSource
from corehq.apps.reports.sqlreport import DataFormatter, DictDataFormat
from corehq.apps.userreports.decorators import catch_and_raise_exceptions
from corehq.apps.userreports.mixins import ConfigurableReportDataSourceMixin
from corehq.apps.userreports.util import get_indicator_adapter
from dimagi.utils.modules import to_function


class ConfigurableReportCustomDataSource(ConfigurableReportDataSourceMixin, ReportDataSource):
    @property
    @memoized
    def helper(self):
        if self.config.backend_id == 'SQL':
            return ConfigurableReportCustomSQLDataSourceHelper(self)

    def set_provider(self, provider_string):
        self._provider = to_function(provider_string, failhard=True)(self)

    @property
    def columns(self):
        db_columns = [c for conf in self.column_configs for c in conf.columns]
        return db_columns

    @memoized
    @method_decorator(catch_and_raise_exceptions)
    def get_data(self, start=None, limit=None):
        ret = self._provider.get_data(self, start, limit)
        formatter = DataFormatter(DictDataFormat(self.columns, no_value=None))
        formatted_data = list(formatter.format(ret, group_by=self.group_by).values())

        for report_column in self.top_level_db_columns:
            report_column.format_data(formatted_data)

        for computed_column in self.top_level_computed_columns:
            for row in formatted_data:
                row[computed_column.column_id] = computed_column.wrapped_expression(row)

        return formatted_data

    @method_decorator(catch_and_raise_exceptions)
    def get_total_records(self):
        return self._provider.get_total_records(self)

    @method_decorator(catch_and_raise_exceptions)
    def get_total_row(self):
        return self._provider.get_total_row(self)


class ConfigurableReportCustomSQLDataSourceHelper(object):
    def __init__(self, report_data_source):
        self.report_data_source = report_data_source
        self.adapter = get_indicator_adapter(self.report_data_source.config)

    def session_helper(self):
        return self.adapter.session_helper

    def get_table(self):
        return self.adapter.get_table()

    @property
    def _filters(self):
        return [
            _f
            for _f in [
                fv.to_sql_filter() for fv in self.report_data_source._filter_values.values()
            ]
            if _f
        ]

    @property
    def sql_alchemy_filters(self):
        return [f.build_expression(self.get_table()) for f in self._filters if f]

    @property
    def sql_alchemy_filter_values(self):
        return {
            k: v
            for fv in self.report_data_source._filter_values.values()
            for k, v in fv.to_sql_values().items()
        }
