from abc import ABCMeta, abstractmethod

from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    StaticDataSourceConfiguration,
)


class DataSourceProvider(metaclass=ABCMeta):

    def __init__(self, referenced_doc_type=None):
        self.referenced_doc_type = referenced_doc_type

    @abstractmethod
    def get_all_data_sources(self):
        pass

    @abstractmethod
    def by_domain(self, domain):
        pass

    def get_data_sources(self):
        sources = self.get_all_data_sources()
        if self.referenced_doc_type:
            return [source for source in sources if source.referenced_doc_type == self.referenced_doc_type]
        else:
            return sources


class DynamicDataSourceProvider(DataSourceProvider):

    def get_all_data_sources(self):
        return DataSourceConfiguration.view(
            'userreports/active_data_sources', reduce=False, include_docs=True).all()

    def by_domain(self, domain):
        return DataSourceConfiguration.view(
            'userreports/active_data_sources', startkey=[domain], endkey=[domain, {}],
            reduce=False, include_docs=True).all()


class StaticDataSourceProvider(DataSourceProvider):

    def get_all_data_sources(self):
        return StaticDataSourceConfiguration.all()

    def by_domain(self, domain):
        return StaticDataSourceConfiguration.by_domain(domain)


class MockDataSourceProvider(DataSourceProvider):
    # for testing only

    def get_all_data_sources(self):
        return []

    def by_domain(self, domain):
        return []
