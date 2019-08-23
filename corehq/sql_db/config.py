from __future__ import absolute_import
from __future__ import unicode_literals
import json

from django.conf import settings
from jsonobject.api import JsonObject
from jsonobject.properties import IntegerProperty, StringProperty

from memoized import memoized
from six.moves import zip
from .exceptions import PartitionValidationError, NotPowerOf2Error, NonContinuousShardsError, NotZeroStartError, \
    NoSuchShardDatabaseError
from six.moves import range

FORM_PROCESSING_GROUP = 'form_processing'
PROXY_GROUP = 'proxy'
MAIN_GROUP = 'main'

SHARD_OPTION_TEMPLATE = "p{id:04d} 'dbname={dbname} host={host} port={port}'"


class LooslyEqualJsonObject(object):

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self._obj == other._obj

    def __hash__(self):
        return hash(json.dumps(self._obj, sort_keys=True))

    def __ne__(self, other):
        return not self == other


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


class PartitionConfig(object):

    def __init__(self):
        assert settings.USE_PARTITIONED_DATABASE
        self._validate()

    def _validate(self):
        for group, dbs in self.partition_config['groups'].items():
            for db in dbs:
                if db not in self.database_config:
                    raise PartitionValidationError('{} not in found in DATABASES'.format(db))

        shards_seen = set()
        previous_range = None
        for group, shard_range, in sorted(list(self.partition_config['shards'].items()), key=lambda x: x[1]):
            if not previous_range:
                if shard_range[0] != 0:
                    raise NotZeroStartError('Shard numbering must start at 0')
            else:
                if previous_range[1] + 1 != shard_range[0]:
                    raise NonContinuousShardsError(
                        'Shards must be numbered consecutively: {} -> {}'.format(
                            previous_range[1], shard_range[0]
                        ))

            shards_seen |= set(range(shard_range[0], shard_range[1] + 1))
            previous_range = shard_range

        num_shards = len(shards_seen)

        if not _is_power_of_2(num_shards):
            raise NotPowerOf2Error('Total number of shards must be a power of 2: {}'.format(num_shards))

        self._num_shards = num_shards

    @property
    def num_shards(self):
        return self._num_shards

    @property
    def partition_config(self):
        return settings.PARTITION_DATABASE_CONFIG

    @property
    def database_config(self):
        return settings.DATABASES

    def get_proxy_db(self):
        return self._dbs_by_group(PROXY_GROUP, 1)[0]

    def get_main_db(self):
        return self._dbs_by_group(MAIN_GROUP, 1)[0]

    def get_form_processing_dbs(self):
        return self._dbs_by_group(FORM_PROCESSING_GROUP)

    def _dbs_by_group(self, group, check_len=None):
        """Given a database group, returns the list of dbs associated with it"""
        dbs = self.partition_config['groups'][group]
        if check_len:
            assert len(dbs) == check_len
        return dbs

    @memoized
    def _get_django_shards(self):
        shard_config = self.partition_config['shards']
        db_shards = []
        for db, shard_range in shard_config.items():
            db_shards.extend([DbShard(shard_num, db) for shard_num in range(shard_range[0], shard_range[1] + 1)])
        return sorted(db_shards, key=lambda shard: shard.shard_id)

    @memoized
    def get_shards(self):
        """Returns a list of ShardMeta objects sorted by shard ID"""
        host_map = self.partition_config.get('host_map', {})
        db_shards = self._get_django_shards()
        return [shard.to_shard_meta(host_map) for shard in db_shards]

    @memoized
    def get_shards_on_db(self, db):
        """Given a database name, returns a list of the shard ids that are on that database"""
        try:
            shard_range = self.partition_config['shards'][db]
        except KeyError:
            raise NoSuchShardDatabaseError('No database {} found in shard config'.format(db))
        else:
            return list(range(shard_range[0], shard_range[1] + 1))

    @memoized
    def get_django_shard_map(self):
        db_shards = self._get_django_shards()
        return {shard.shard_id: shard for shard in db_shards}


def _is_power_of_2(num):
    return num and not (num & (num - 1))


def parse_existing_shard(shard_option):
    shard_name, options = shard_option.split('=', 1)
    assert shard_name[0] == 'p'
    shard_id = int(shard_name[1:])
    options = options.split(' ')
    option_kwargs = dict(tuple(option.split('=')) for option in options)
    if 'port' in option_kwargs:
        option_kwargs['port'] = int(option_kwargs['port'])
    return ShardMeta(id=shard_id, **option_kwargs)


def get_shards_to_update(existing_shards, new_shards):
    assert len(existing_shards) == len(new_shards)
    shards_to_update = []
    for existing, new in zip(existing_shards, new_shards):
        assert existing.id == new.id, '{} != {}'.format(existing.id, new.id)
        if existing != new:
            shards_to_update.append(new)

    return shards_to_update


def _get_config():
    if settings.USE_PARTITIONED_DATABASE:
        return PartitionConfig()
    else:
        return object()


partition_config = _get_config()
