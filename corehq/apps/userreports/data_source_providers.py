from __future__ import absolute_import
from __future__ import unicode_literals
from abc import ABCMeta, abstractmethod
from corehq.apps.userreports.models import DataSourceConfiguration, StaticDataSourceConfiguration
import six


class DataSourceProvider(six.with_metaclass(ABCMeta, object)):
    @abstractmethod
    def get_data_sources(self):
        pass


class DynamicDataSourceProvider(DataSourceProvider):

    def get_data_sources(self):
        return DataSourceConfiguration.view(
            'userreports/active_data_sources', reduce=False, include_docs=True).all()


class StaticDataSourceProvider(DataSourceProvider):

    def get_data_sources(self):
        return StaticDataSourceConfiguration.all()


class MockDataSourceProvider(DataSourceProvider):
    # for testing only

    def get_data_sources(self):
        return []
