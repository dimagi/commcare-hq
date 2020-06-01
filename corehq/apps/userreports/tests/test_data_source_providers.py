import datetime
from django.test import TestCase, SimpleTestCase

from corehq.apps.userreports.data_source_providers import DynamicDataSourceProvider, MockDataSourceProvider
from corehq.apps.userreports.tests.utils import (
    get_sample_data_source,
)


class DataSourceProviderTest(TestCase):

    def test_dynamic_modified_date(self):
        config = get_sample_data_source()
        timestamp_before_save = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
        config.save()
        self.addCleanup(config.delete)
        timestamp_after_save = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
        provider = DynamicDataSourceProvider()
        providers = provider.get_data_sources_modified_since(timestamp_before_save)
        self.assertEqual(1, len(providers))
        self.assertEqual(config._id, providers[0]._id)
        providers = provider.get_data_sources_modified_since(timestamp_after_save)
        self.assertEqual(0, len(providers))


class MockDataSourceProviderTest(SimpleTestCase):

    def test_empty(self):
        provider = MockDataSourceProvider()
        self.assertEqual([], provider.get_all_data_sources())
        self.assertEqual([], provider.by_domain('foo'))
        self.assertEqual([], provider.get_data_sources_modified_since(datetime.datetime.utcnow()))

    def test_with_data(self):
        ds_1 = object()
        ds_2 = object()
        ds_3 = object()
        provider = MockDataSourceProvider({
            'domain1': [ds_1, ds_2],
            'domain2': [ds_3],
        })
        self.assertEqual({ds_1, ds_2, ds_3}, set(provider.get_all_data_sources()))
        self.assertEqual([ds_1, ds_2], provider.by_domain('domain1'))
        self.assertEqual([ds_3], provider.by_domain('domain2'))
        self.assertEqual([], provider.by_domain('domain3'))
