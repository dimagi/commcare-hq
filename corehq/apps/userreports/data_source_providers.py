from __future__ import absolute_import
from abc import ABCMeta, abstractmethod
from corehq.apps.userreports.models import DataSourceConfiguration, StaticDataSourceConfiguration
import six

from corehq.apps.userreports.util import get_data_source_configurations


class DataSourceProvider(six.with_metaclass(ABCMeta, object)):
    @abstractmethod
    def get_data_sources(self):
        pass


class DynamicDataSourceProvider(DataSourceProvider):

    def get_data_sources(self):
        return get_data_source_configurations()


class StaticDataSourceProvider(DataSourceProvider):

    def get_data_sources(self):
        return StaticDataSourceConfiguration.all()


class MockDataSourceProvider(DataSourceProvider):
    # for testing only

    def get_data_sources(self):
        return []
