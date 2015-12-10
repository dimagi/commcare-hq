from collections import namedtuple

from django.conf import settings
from .exceptions import PartitionValidationError, NotPowerOf2Error, NonContinuousShardsError, NotZeroStartError

FORM_PROCESSING_GROUP = 'form_processing'
PROXY_GROUP = 'proxy'
MAIN_GROUP = 'main'


DbShard = namedtuple('DbShard', ['shard_number', 'db_name'])


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
        for group, shard_range, in sorted(self.partition_config['shards'].items(), key=lambda x: x[0]):
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
            raise NotPowerOf2Error('Total number of shards must be a power of 2')

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

    def get_shards(self):
        """Returns the shard_number mapped to database"""
        shard_config = self.partition_config['shards']
        shards = []
        for db, shard_range in shard_config.items():
            shards.extend([DbShard(shard_num, db) for shard_num in range(shard_range[0], shard_range[1] + 1)])
        return sorted(shards, key=lambda shard: shard.shard_number)


def _is_power_of_2(num):
    return num and not (num & (num - 1))
