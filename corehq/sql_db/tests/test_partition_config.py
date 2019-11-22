import copy

from django.db import DEFAULT_DB_ALIAS
from django.test import SimpleTestCase
from django.test.utils import override_settings

from testil import assert_raises

from corehq.sql_db.config import (
    PlProxyConfig,
    ShardMeta,
    _get_shard_count,
    _get_standby_plproxy_config,
)
from corehq.sql_db.exceptions import PartitionValidationError
from corehq.sql_db.management.commands.configure_pl_proxy_cluster import (
    get_shards_to_update,
    parse_existing_shard,
)

from ..exceptions import (
    NonContinuousShardsError,
    NoSuchShardDatabaseError,
    NotPowerOf2Error,
    NotZeroStartError,
)

db_dict = {'NAME': 'commcarehq', 'USER': 'commcarehq', 'HOST': 'hqdb0', 'PORT': 5432}
TEST_DATABASES = {
    DEFAULT_DB_ALIAS: db_dict.copy(),
    'proxy': db_dict.copy(),
    'db1': {'NAME': 'db1', 'USER': 'commcarehq', 'HOST': 'hqdb1', 'PORT': 5432},
    'db2': {'NAME': 'db2', 'USER': 'commcarehq', 'HOST': 'hqdb2', 'PORT': 5432},
}


def _get_partition_config(shard_config):
    databases = copy.deepcopy(TEST_DATABASES)
    databases['proxy']['PLPROXY'] = {'PROXY': True}
    for db, config in databases.items():
        if db in shard_config:
            config['PLPROXY'] = {
                'SHARDS': shard_config[db]
            }
    return databases


TEST_LEGACY_FORMAT_GROUPS = {
    'shards': {
        'db1': [0, 1],
        'db2': [2, 3],
    },
    'groups': {
        'proxy': ['proxy'],
        'form_processing': ['db1', 'db2'],
    }
}

TEST_LEGACY_FORMAT = {
    'shards': {
        'db1': [0, 1],
        'db2': [2, 3],
    },
    'proxy': 'proxy'
}

TEST_PARTITION_CONFIG = _get_partition_config({
    'db1': [0, 1],
    'db2': [2, 3],
})

TEST_PARTITION_CONFIG_HOST_MAP = _get_partition_config({
    'db1': [0, 0],
    'db2': [1, 1],
})
TEST_PARTITION_CONFIG_HOST_MAP['db1']['PLPROXY']['PLPROXY_HOST'] = 'localhost'

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

PARTITION_CONFIG_WITH_STANDBYS = databases = _get_partition_config({
    'db1': [0, 1],
    'db2': [2, 3],
})
PARTITION_CONFIG_WITH_STANDBYS.update({
    'db1_standby': {'STANDBY': {'MASTER': 'db1'}},
    'db2_standby': {'STANDBY': {'MASTER': 'db2'}},
})


@override_settings(DATABASES=TEST_DATABASES, USE_PARTITIONED_DATABASE=True)
class TestPartitionConfig(SimpleTestCase):

    def test_num_shards(self):
        self.assertEqual(4, _get_shard_count([[0, 1], [2, 3]]))

    def test_dbs_by_group(self):
        config = PlProxyConfig.from_dict(TEST_PARTITION_CONFIG)
        self.assertIn('db1', config.shard_map)
        self.assertIn('db2', config.shard_map)

    def test_shard_mapping(self):
        config = PlProxyConfig.from_dict(TEST_PARTITION_CONFIG)
        shards = config.get_shards()
        self.assertEqual(shards, [
            ShardMeta(id=0, dbname='db1', host='hqdb1', port=5432),
            ShardMeta(id=1, dbname='db1', host='hqdb1', port=5432),
            ShardMeta(id=2, dbname='db2', host='hqdb2', port=5432),
            ShardMeta(id=3, dbname='db2', host='hqdb2', port=5432),
        ])

    def test_get_shards_on_db(self):
        config = PlProxyConfig.from_dict(TEST_PARTITION_CONFIG)
        self.assertEqual([0, 1], config.get_shards_on_db('db1'))
        self.assertEqual([2, 3], config.get_shards_on_db('db2'))

    def test_get_shards_on_db_not_found(self):
        config = PlProxyConfig.from_dict(TEST_PARTITION_CONFIG)
        with self.assertRaises(NoSuchShardDatabaseError):
            config.get_shards_on_db('db3')

    def test_host_map(self):
        config = PlProxyConfig.from_dict(TEST_PARTITION_CONFIG_HOST_MAP)
        shards = config.get_shards()
        self.assertEqual(shards, [
            ShardMeta(id=0, dbname='db1', host='localhost', port=5432),
            ShardMeta(id=1, dbname='db2', host='hqdb2', port=5432),
        ])

    def test_legacy_format(self):
        config = PlProxyConfig.from_legacy_dict(TEST_LEGACY_FORMAT)
        self.assertEqual('proxy', config.proxy_db)
        self.assertEqual({'db1', 'db2'}, set(config.form_processing_dbs))

    def test_get_standby_plproxy_config(self):
        primary_config = PlProxyConfig.from_dict(PARTITION_CONFIG_WITH_STANDBYS)
        with override_settings(DATABASES=PARTITION_CONFIG_WITH_STANDBYS):
            standby_config = _get_standby_plproxy_config(primary_config)
        self.assertEqual('commcarehq_standby', standby_config.cluster_name)
        self.assertEqual('proxy', standby_config.proxy_db)
        self.assertEqual({'db1_standby', 'db2_standby'}, set(standby_config.form_processing_dbs))
        self.assertEqual(primary_config.shard_count, standby_config.shard_count)

    def test_get_standby_plproxy_config_missing_standby(self):
        databases = copy.deepcopy(PARTITION_CONFIG_WITH_STANDBYS)
        del databases['db1_standby']  # remove one standby

        primary_config = PlProxyConfig.from_dict(databases)
        with override_settings(DATABASES=databases), self.assertRaises(PartitionValidationError):
            _get_standby_plproxy_config(primary_config)

    def test_get_standby_plproxy_config_misconfigured(self):
        databases = copy.deepcopy(PARTITION_CONFIG_WITH_STANDBYS)
        databases['db1_standby']['PLPROXY'] = {}  # add plproxy config to a standby

        primary_config = PlProxyConfig.from_dict(databases)
        with override_settings(DATABASES=databases), self.assertRaises(PartitionValidationError):
            _get_standby_plproxy_config(primary_config)


def test_partition_config_validation():
    def _run_test(config, exception, message):
        settings = {
            'DATABASES': TEST_DATABASES,
        }
        with override_settings(**settings), assert_raises(exception, msg=message):
            PlProxyConfig.from_dict(config)

    cases = [
        (INVALID_SHARD_RANGE_START, NotZeroStartError, None),
        (INVALID_SHARD_RANGE_CONTINUOUS, NonContinuousShardsError, None),
        (INVALID_SHARD_RANGE_POWER_2, NotPowerOf2Error, None),
    ]
    for config, exception, message in cases:
        yield _run_test, config, exception, message


@override_settings(DATABASES=TEST_DATABASES)
class PlProxyTests(SimpleTestCase):

    def test_get_server_option_string(self):
        self.assertEqual(
            "p0000 'dbname=db1 host=hqdb0 port=5432'",
            ShardMeta(id=0, dbname='db1', host='hqdb0', port=5432).get_server_option_string()
        )

    def test_parse_existing_shard(self):
        parsed = parse_existing_shard('p0001=dbname=db1 host=hqdb0 port=5432')
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
