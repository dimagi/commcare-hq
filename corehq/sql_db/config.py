import copy
import json
import logging
from typing import Optional

from django.conf import settings

import attr
from jsonobject.api import JsonObject
from jsonobject.properties import IntegerProperty, StringProperty
from memoized import memoized

from .exceptions import (
    NonContinuousShardsError,
    NoSuchShardDatabaseError,
    NotPowerOf2Error,
    NotZeroStartError,
    PartitionValidationError,
)

FORM_PROCESSING_GROUP = 'form_processing'
PROXY_GROUP = 'proxy'

SHARD_OPTION_TEMPLATE = "p{id:04d} 'dbname={dbname} host={host} port={port}'"

logger = logging.getLogger(__name__)


class LooslyEqualJsonObject(object):

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self._obj == other._obj

    def __hash__(self):
        return hash(json.dumps(self._obj, sort_keys=True))


class ShardMeta(JsonObject, LooslyEqualJsonObject):
    id = IntegerProperty()
    dbname = StringProperty()
    host = StringProperty()
    port = IntegerProperty()

    def get_server_option_string(self):
        return SHARD_OPTION_TEMPLATE.format(**self)


class DbShard(object):

    def __init__(self, shard_id, django_dbname):
        self.shard_id = shard_id
        self.django_dbname = django_dbname

    def to_shard_meta(self, host_map):
        config = settings.DATABASES[self.django_dbname]
        host = host_map.get(config['HOST'], config['HOST'])
        return ShardMeta(
            id=self.shard_id,
            dbname=config['NAME'],
            host=host,
            port=int(config['PORT']),
        )


@attr.s
class PlProxyConfig(object):
    cluster_name = attr.ib()
    proxy_db = attr.ib()
    shard_map = attr.ib()
    # 'host_map' is use to support Docker where external connections are via the docker name
    # but internal connections are to 'localhost'. See docker/localsettings.py
    host_map = attr.ib()
    shard_count = attr.ib()

    @property
    def form_processing_dbs(self):
        return list(self.shard_map)

    @memoized
    def _get_django_shards(self):
        shard_map = self.shard_map
        db_shards = []
        for db, shard_range in shard_map.items():
            db_shards.extend([DbShard(shard_num, db) for shard_num in range(shard_range[0], shard_range[1] + 1)])
        return sorted(db_shards, key=lambda shard: shard.shard_id)

    @memoized
    def get_shards(self):
        """Returns a list of ShardMeta objects sorted by shard ID"""
        host_map = self.host_map
        db_shards = self._get_django_shards()
        return [shard.to_shard_meta(host_map) for shard in db_shards]

    @memoized
    def get_shards_on_db(self, db):
        """Given a database name, returns a list of the shard ids that are on that database"""
        try:
            shard_range = self.shard_map[db]
        except KeyError:
            raise NoSuchShardDatabaseError('No database {} found in shard config'.format(db))
        else:
            return list(range(shard_range[0], shard_range[1] + 1))

    @memoized
    def get_django_shard_map(self):
        db_shards = self._get_django_shards()
        return {shard.shard_id: shard for shard in db_shards}

    @classmethod
    def from_settings(cls):
        assert settings.USE_PARTITIONED_DATABASE
        return (
            PlProxyConfig.from_dict(settings.DATABASES)
            or PlProxyConfig.from_legacy_dict(settings.PARTITION_DATABASE_CONFIG)
        )

    @classmethod
    def from_dict(cls, config_dict):
        """Get config from Django DATABASES dict. Custom porperties in DATABASE config:

        DATABASES = {
            'db1': {
                ...
                'PLPROXY': {
                    'SHARDS': [0, 1]  # Shard range for this DB
                    'PLPROXY_HOST': 'other'  # re-map host in plproxy cluster config
                    'PROXY': False  # True if this DB is the proxy DB
                }
            }
        }
        """
        proxy_db = None
        shard_map = {}
        host_map = {}
        has_config = False
        for alias, config in config_dict.items():
            plproxy_config = config.get('PLPROXY', {})
            if not plproxy_config:
                continue

            has_config = True
            if plproxy_config.get('PROXY'):
                if proxy_db:
                    raise PartitionValidationError('Multiple plproxy databases specified', proxy_db, alias)
                proxy_db = alias

            shards = plproxy_config.get('SHARDS')
            if shards:
                shard_map[alias] = shards

            # 'host_map' is use to support Docker where external connections are via the docker name
            # but internal connections are to 'localhost'. See docker/localsettings.py
            mapped_host = plproxy_config.get('PLPROXY_HOST')
            if mapped_host:
                host_map[config['HOST']] = mapped_host

        if not has_config:
            return

        config = PlProxyConfig(
            settings.PL_PROXY_CLUSTER_NAME,
            proxy_db, shard_map, host_map, _get_shard_count(shard_map.values())
        )
        config.validate()
        return config

    @classmethod
    def from_legacy_dict(cls, legacy_config):
        """Legacy format spec:
        ```
        config = {
            'shards': {
                'db1': [0, 1],
                'db2': [2, 3],
            },
            'proxy': 'proxy'
        }
        ```"""
        if not legacy_config:
            return

        if 'groups' in legacy_config:
            # convert old format
            proxy_db = legacy_config['groups']['proxy'][0]
        else:
            proxy_db = legacy_config['proxy']
        shard_map = legacy_config['shards']
        host_map = legacy_config.get('host_map', {})

        config = PlProxyConfig(
            settings.PL_PROXY_CLUSTER_NAME,
            proxy_db, shard_map, host_map, _get_shard_count(shard_map.values())
        )
        config.validate()
        return config

    def validate(self):
        if self.proxy_db not in settings.DATABASES:
            raise PartitionValidationError(f'{self.proxy_db} not in found in DATABASES')

        previous_range = None
        for group, shard_range, in sorted(list(self.shard_map.items()), key=lambda x: x[1]):
            if not previous_range:
                if shard_range[0] != 0:
                    raise NotZeroStartError('Shard numbering must start at 0')
            else:
                if previous_range[1] + 1 != shard_range[0]:
                    raise NonContinuousShardsError(
                        'Shards must be numbered consecutively: {} -> {}'.format(
                            previous_range[1], shard_range[0]
                        ))

            previous_range = shard_range

        if not _is_power_of_2(self.shard_count):
            raise NotPowerOf2Error('Total number of shards must be a power of 2: {}'.format(self.shard_count))


def _is_power_of_2(num):
    return num and not (num & (num - 1))


def _get_shard_count(shard_ranges):
    shards = set()
    for shard_range in shard_ranges:
        shards |= set(range(shard_range[0], shard_range[1] + 1))
    return len(shards)


def _get_standby_plproxy_config(primary_config: PlProxyConfig) -> Optional[PlProxyConfig]:
    """
    Create plproxy config for querying standbys. This assumes that the main plproxy DB
    will be the same as the primary DB.

    This does not support multiple standby databases per primary.

    :returns: PlProxyConfig object with details of all the standby databases
              or None if no standby databases are configured

    :raises: PartitionValidationError if a partial set of standby databases could be found.
    """

    proxy_for_standbys = None
    for db_alias, config in settings.DATABASES.items():
        if config.get('PLPROXY', {}).get('PROXY_FOR_STANDBYS'):
            proxy_for_standbys = db_alias
            break

    if not proxy_for_standbys:
        return

    standbys_by_primary = {
        config['STANDBY']['MASTER']: db
        for db, config in settings.DATABASES.items()
        if config.get('STANDBY', {}).get('MASTER')
    }

    proxy_config = copy.deepcopy(settings.DATABASES[proxy_for_standbys])
    proxy_config['PLPROXY']['PROXY'] = True
    standby_db_config = {
        proxy_for_standbys: proxy_config
    }

    def _convert_primary_config(primary_db):
        standby = standbys_by_primary.get(primary_db)
        if standby:
            config = copy.deepcopy(settings.DATABASES[standby])
            if 'PLPROXY' in config:
                raise PartitionValidationError('Standby databases should not have PLPROXY configuration')
            config['PLPROXY'] = {
                'SHARDS': primary_config.shard_map[primary_db]
            }

            standby_db_config[standby] = config
            return True

    standbys_found = [
        _convert_primary_config(db)
        for db in primary_config.form_processing_dbs
    ]

    if not all(standbys_found):
        missing = [db for found, db in zip(standbys_found, primary_config.form_processing_dbs) if not found]
        raise PartitionValidationError(f'Not all shard DBs have standbys configured {missing}')

    return PlProxyConfig.from_dict(standby_db_config)


plproxy_config = None
plproxy_standby_config = None
if settings.USE_PARTITIONED_DATABASE:
    plproxy_config = PlProxyConfig.from_settings()
    try:
        plproxy_standby_config = _get_standby_plproxy_config(plproxy_config)
    except PartitionValidationError:
        logger.exception('Error in PLPROXY standby configuration')
