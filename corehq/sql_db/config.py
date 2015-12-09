from django.conf import settings
from .exceptions import PartitionValidationError

FORM_PROCESSING_GROUP = 'form_processing'
PROXY_GROUP = 'proxy'
MAIN_GROUP = 'main'


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
        for group, shard_range, in self.partition_config['shards'].items():
            current_shards = set(range(shard_range[0], shard_range[1] + 1))
            if shards_seen & current_shards:
                raise PartitionValidationError('{} has shards that other dbs point to'.format(group))
            shards_seen |= current_shards

        num_shards = len(shards_seen)

        if not _is_power_of_2(num_shards):
            raise PartitionValidationError('Total number of shards must be a power of 2')

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

    def shard_mapping(self):
        """Returns the shard_number mapped to database"""
        shards = self.partition_config['shards']
        shard_mapping = {}
        for db, shard_range in shards.items():
            shard_mapping.update({shard: db for shard in range(shard_range[0], shard_range[1] + 1)})
        return shard_mapping


def _is_power_of_2(num):
    return num and not (num & (num - 1))
