from django.conf import settings

from .exceptions import PartitionValidationError


class PartitionConfig(object):

    def __init__(self):
        self._validate()

    def _validate(self):
        for group, dbs in self.partition_config['groups'].items():
            for db in dbs:
                if db not in self.database_config:
                    raise PartitionValidationError('{} not in found in DATABASES'.format(db))

        shards_seen = set()
        for group, shard_range, in self.partition_config['shards'].items():
            current_shards = set(range(*shard_range))
            if shards_seen & current_shards:
                raise PartitionValidationError('{} has shards that other dbs point to'.format(group))
            shards_seen |= current_shards

    @property
    def partition_config(self):
        return settings.PARTITION_DATABASE_CONFIG

    @property
    def database_config(self):
        return settings.DATABASES

    def dbs_by_group(self, group):
        """Given a database group, returns the list of dbs associated with it"""
        return self.partition_config['groups'][group]

    def shard_mapping(self):
        """Returns the shard_number mapped to database"""
        shards = self.partition_config['shards']
        shard_mapping = {}
        for db, shard_range in shards.items():
            shard_mapping.update({shard: db for shard in range(*shard_range)})
        return shard_mapping
