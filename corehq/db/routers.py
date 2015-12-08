from .config import PartitionConfig


class PartitionRouter(object):

    def __init__(self):
        self.config = PartitionConfig()

    def allow_migrate(self, db, app_label, model=None, **hints):
        if app_label == 'sql_proxy_accessors':
            return (db in self.config.dbs_by_group('sql_proxy_accessors') or
                    db in self.config.dbs_by_group('sql_accessors'))
        elif app_label == 'sql_accessors':
            return db in self.config.dbs_by_group('sql_accessors')
        else:
            return db in self.config.dbs_by_group('main')


class MonolithRouter(object):

    def __init__(self):
        self.config = PartitionConfig()

    def allow_migrate(self, db, app_label, model=None, **hints):
        if app_label == 'sql_proxy_accessors':
            return False
        return True
