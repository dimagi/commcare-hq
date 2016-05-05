from abc import ABCMeta, abstractmethod
from corehq.apps.userreports.models import DataSourceConfiguration, StaticDataSourceConfiguration


class DataSourceProvider(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def get_data_sources(self):
        pass


class DynamicDataSourceProvider(DataSourceProvider):

    def get_data_sources(self):
        return filter(lambda config: not config.is_deactivated, DataSourceConfiguration.all())


class StaticDataSourceProvider(DataSourceProvider):

    def get_data_sources(self):
        return StaticDataSourceConfiguration.all()


class MockDataSourceProvider(DataSourceProvider):
    # for testing only

    def get_data_sources(self):
        return []
