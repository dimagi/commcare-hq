from django.test import SimpleTestCase
from django.test.utils import override_settings

from ..config import PartitionConfig

TEST_PARTITION_CONFIG = {
    'shards': {
        'default': {
            'start': 0,
            'end': 100,
        }
    },
    'groups': {
        'main': ['default'],
        'proxy': ['proxy'],
        'form_processing': ['db1', 'db2'],
    }
}

TEST_DATABASES = {
    'default': {
        'NAME': 'commcarehq',
        'USER': 'commcarehq',
    },
    'proxy': {
        'NAME': 'commcarehq',
        'USER': 'commcarehq',
    },
    'db1': {
        'NAME': 'commcarehq',
        'USER': 'commcarehq',
    },
    'db2': {
        'NAME': 'commcarehq',
        'USER': 'commcarehq',
    },
}


class TestPartitionConfig(SimpleTestCase):

    @override_settings(PARTITION_DATABASE_CONFIG=TEST_PARTITION_CONFIG)
    @override_settings(DATABASES=TEST_DATABASES)
    def test_dbs_by_group(self):
        config = PartitionConfig()
        dbs = config.dbs_by_group('form_processing')
        self.assertIn('db1', dbs)
        self.assertIn('db2', dbs)
