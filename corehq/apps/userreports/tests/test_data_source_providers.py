import datetime
from django.test import TestCase

from corehq.apps.userreports.data_source_providers import DynamicDataSourceProvider
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
