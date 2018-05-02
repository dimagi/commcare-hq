from __future__ import absolute_import
from __future__ import unicode_literals

from django.utils.decorators import method_decorator
from memoized import memoized

from corehq.apps.reports.api import ReportDataSource
from corehq.apps.userreports.decorators import catch_and_raise_exceptions
from corehq.apps.userreports.mixins import ConfigurableReportDataSourceMixin
from dimagi.utils.modules import to_function


class ConfigurableReportCustomDataSource(ConfigurableReportDataSourceMixin, ReportDataSource):
    def set_provider(self, provider_string):
        self._provider = to_function(provider_string, failhard=True)

    @property
    def filters(self):
        pass

    @property
    def order_by(self):
        pass

    @property
    def columns(self):
        pass

    @memoized
    @method_decorator(catch_and_raise_exceptions)
    def get_data(self, start=None, limit=None):
        return self._provider.get_data(start, limit)

    @method_decorator(catch_and_raise_exceptions)
    def get_total_records(self):
        return self._provider.get_total_records()

    @method_decorator(catch_and_raise_exceptions)
    def get_total_row(self):
        return self._provider.get_total_row()
