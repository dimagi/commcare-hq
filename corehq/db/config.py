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

    @property
    def partition_config(self):
        return settings.PARTITION_DATABASE_CONFIG

    @property
    def database_config(self):
        return settings.DATABASES

    def dbs_by_group(self, group):
        return self.partition_config['groups'][group]
