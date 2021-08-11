from abc import ABCMeta, abstractmethod

from corehq.apps.userreports.dbaccessors import get_all_registry_data_source_ids, \
    get_registry_data_sources_modified_since
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    StaticDataSourceConfiguration, RegistryDataSourceConfiguration,
)
from dimagi.utils.couch.database import iter_docs


class DataSourceProvider(metaclass=ABCMeta):

    def __init__(self, referenced_doc_type=None):
        self.referenced_doc_type = referenced_doc_type

    @abstractmethod
    def get_all_data_sources(self):
        """Return a list of active data sources"""
        pass

    @abstractmethod
    def get_data_sources_modified_since(self, timestamp):
        """Return a list of active data sources modified since the given timestamp"""
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

    def get_data_sources_modified_since(self, timestamp):
        return DataSourceConfiguration.view(
            'userreports/data_sources_by_last_modified',
            startkey=[timestamp.isoformat()],
            endkey=[{}],
            reduce=False,
            include_docs=True
        ).all()


class RegistryDataSourceProvider(DataSourceProvider):

    def get_all_data_sources(self):
        active_ids = get_all_registry_data_source_ids(is_active=True)
        for result in iter_docs(RegistryDataSourceConfiguration.get_db(), active_ids):
            yield RegistryDataSourceConfiguration.wrap(result)

    def get_data_sources_modified_since(self, timestamp):
        return get_registry_data_sources_modified_since(timestamp)


class StaticDataSourceProvider(DataSourceProvider):

    def get_all_data_sources(self):
        return StaticDataSourceConfiguration.all()

    def get_data_sources_modified_since(self, timestamp):
        return []


class MockDataSourceProvider(DataSourceProvider):
    # for testing only
    def __init__(self, data_sources_by_domain=None, referenced_doc_type=None):
        self.referenced_doc_type = referenced_doc_type
        self.data_sources_by_domain = data_sources_by_domain or {}

    def get_all_data_sources(self):
        return [ds for domain, domain_sources in self.data_sources_by_domain.items() for ds in domain_sources]

    def get_data_sources_modified_since(self, timestamp):
        return []
