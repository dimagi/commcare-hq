from django.test import SimpleTestCase
from django.test.utils import override_settings

from corehq.sql_db.config import DbShard
from corehq.sql_db.management.commands.configure_pl_proxy_cluster import get_shard_config_strings
from ..config import PartitionConfig
from ..exceptions import PartitionValidationError, NotPowerOf2Error, NotZeroStartError, NonContinuousShardsError, \
    ShardOverlapError


def _get_partition_config(shard_config):
    return {
        'shards': shard_config,
        'groups': {
            'main': ['default'],
            'proxy': ['proxy'],
            'form_processing': ['db1', 'db2'],
        }
    }

TEST_PARTITION_CONFIG = _get_partition_config({
    'db1': [0, 1],
    'db2': [2, 3],
})

INVALID_SHARD_RANGE_START = _get_partition_config({
    'db1': [1, 2],
    'db2': [3, 4],
})

INVALID_SHARD_RANGE_CONTINUOUS = _get_partition_config({
    'db1': [0, 4],
    'db2': [7, 8],
})

INVALID_SHARD_RANGE_POWER_2 = _get_partition_config({
    'db1': [0, 4],
    'db2': [5, 9],
})

db_dict = {'NAME': 'commcarehq', 'USER': 'commcarehq', 'HOST': 'hqdb0', 'PORT': 5432}
TEST_DATABASES = {
    'default': db_dict,
    'proxy': db_dict,
    'db1': {'NAME': 'db1', 'USER': 'commcarehq', 'HOST': 'hqdb0', 'PORT': 5432},
    'db2': {'NAME': 'db2', 'USER': 'commcarehq', 'HOST': 'hqdb0', 'PORT': 5432},
}


@override_settings(USE_PARTITIONED_DATABASE=True)
@override_settings(PARTITION_DATABASE_CONFIG=TEST_PARTITION_CONFIG)
@override_settings(DATABASES=TEST_DATABASES)
class TestPartitionConfig(SimpleTestCase):

    def test_dbs_by_group(self):
        config = PartitionConfig()
        dbs = config.get_form_processing_dbs()
        self.assertIn('db1', dbs)
        self.assertIn('db2', dbs)

    def test_shard_mapping(self):
        config = PartitionConfig()
        shards = config.get_shards()
        self.assertEquals(shards, [
            DbShard(0, 'db1'),
            DbShard(1, 'db1'),
            DbShard(2, 'db2'),
            DbShard(3, 'db2'),
        ])

    @override_settings(PARTITION_DATABASE_CONFIG=INVALID_SHARD_RANGE_START)
    def test_invalid_shard_range_start(self):
        with self.assertRaises(NotZeroStartError):
            PartitionConfig()

    @override_settings(PARTITION_DATABASE_CONFIG=INVALID_SHARD_RANGE_CONTINUOUS)
    def test_invalid_shard_range_continuous(self):
        with self.assertRaises(NonContinuousShardsError):
            PartitionConfig()

    @override_settings(PARTITION_DATABASE_CONFIG=INVALID_SHARD_RANGE_POWER_2)
    def test_invalid_shard_range_power_2(self):
        with self.assertRaises(NotPowerOf2Error):
            PartitionConfig()


@override_settings(DATABASES=TEST_DATABASES)
class PlProxyTests(SimpleTestCase):
    def test_get_shard_config_strings(self):
        shards = [
            DbShard(0, 'db1'),
            DbShard(1, 'db1'),
            DbShard(2, 'db2'),
        ]
        configs = get_shard_config_strings(shards)
        self.assertEqual(3, len(configs))
        self.assertIn("p0 'dbname=test_db1 host=hqdb0 port=5432'", configs)
        self.assertIn("p1 'dbname=test_db1 host=hqdb0 port=5432'", configs)
        self.assertIn("p2 'dbname=test_db2 host=hqdb0 port=5432'", configs)
