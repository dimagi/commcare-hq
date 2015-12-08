from .config import PartitionConfig

PROXY_APP = 'sql_proxy_accessors'
SQL_ACCESSORS_APP = 'sql_accessors'

FORM_PROCESSING_GROUP = 'form_processing'
PROXY_GROUP = 'proxy'
MAIN_GROUP = 'main'


class PartitionRouter(object):

    def __init__(self):
        self.config = PartitionConfig()

    def allow_migrate(self, db, app_label, model=None, **hints):
        if app_label == PROXY_APP:
            return (db in self.config.dbs_by_group(PROXY_GROUP) or
                    db in self.config.dbs_by_group(FORM_PROCESSING_GROUP))
        elif app_label == SQL_ACCESSORS_APP:
            return db in self.config.dbs_by_group(FORM_PROCESSING_GROUP)
        else:
            return db in self.config.dbs_by_group(MAIN_GROUP)


class MonolithRouter(object):

    def allow_migrate(self, db, app_label, model=None, **hints):
        return app_label != PROXY_APP
