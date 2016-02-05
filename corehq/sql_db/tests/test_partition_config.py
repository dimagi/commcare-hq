from django.test import SimpleTestCase
from django.test.utils import override_settings

from corehq.sql_db.config import parse_existing_shard, ShardMeta, get_shards_to_update
from ..config import PartitionConfig
from ..exceptions import NotPowerOf2Error, NotZeroStartError, NonContinuousShardsError


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

TEST_PARTITION_CONFIG_HOST_MAP = _get_partition_config({
    'db1': [0, 0],
    'db2': [1, 1],
})
TEST_PARTITION_CONFIG_HOST_MAP['host_map'] = {
    'hqdb1': 'localhost'
}

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
    'db1': {'NAME': 'db1', 'USER': 'commcarehq', 'HOST': 'hqdb1', 'PORT': 5432},
    'db2': {'NAME': 'db2', 'USER': 'commcarehq', 'HOST': 'hqdb2', 'PORT': 5432},
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
            ShardMeta(id=0, dbname='test_db1', host='hqdb1', port=5432),
            ShardMeta(id=1, dbname='test_db1', host='hqdb1', port=5432),
            ShardMeta(id=2, dbname='test_db2', host='hqdb2', port=5432),
            ShardMeta(id=3, dbname='test_db2', host='hqdb2', port=5432),
        ])

    @override_settings(PARTITION_DATABASE_CONFIG=TEST_PARTITION_CONFIG_HOST_MAP)
    def test_host_map(self):
        config = PartitionConfig()
        shards = config.get_shards()
        self.assertEquals(shards, [
            ShardMeta(id=0, dbname='test_db1', host='localhost', port=5432),
            ShardMeta(id=1, dbname='test_db2', host='hqdb2', port=5432),
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
    dependent_apps = []

    def test_get_server_option_string(self):
        self.assertEqual(
            "p0 'dbname=test_db1 host=hqdb0 port=5432'",
            ShardMeta(id=0, dbname='test_db1', host='hqdb0', port=5432).get_server_option_string()
        )

    def test_parse_existing_shard(self):
        parsed = parse_existing_shard('p1=dbname=db1 host=hqdb0 port=5432')
        self.assertEqual(ShardMeta(id=1, dbname='db1', host='hqdb0', port=5432), parsed)

        parsed = parse_existing_shard('p25=dbname=db2 host=hqdb1 port=6432')
        self.assertEqual(ShardMeta(id=25, dbname='db2', host='hqdb1', port=6432), parsed)

    def test_get_shards_to_update(self):
        existing = [
            ShardMeta(id=0, dbname='db0', host='hqdb0', port=5432),
            ShardMeta(id=1, dbname='db0', host='hqdb0', port=5432),
            ShardMeta(id=2, dbname='db1', host='hqdb1', port=5432),
            ShardMeta(id=3, dbname='db1', host='hqdb1', port=5432),
        ]
        new = [
            ShardMeta(id=0, dbname='db0', host='hqdb0', port=5432),
            ShardMeta(id=1, dbname='db2', host='hqdb2', port=5432),  # changed
            ShardMeta(id=2, dbname='db1', host='hqdb1', port=5432),
            ShardMeta(id=3, dbname='db3', host='hqdb3', port=5432),  # changed
        ]
        to_update = get_shards_to_update(existing, new)
        self.assertEqual([new[1], new[3]], to_update)
