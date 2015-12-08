from .config import PartitionConfig

PROXY_APP = 'sql_proxy_accessors'
SQL_ACCESSORS_APP = 'sql_accessors'


class PartitionRouter(object):

    def __init__(self):
        self.config = PartitionConfig()

    def allow_migrate(self, db, app_label, model=None, **hints):
        if app_label == PROXY_APP:
            return (db == self.config.get_proxy_db or
                    db in self.config.get_form_processing_dbs)
        elif app_label == SQL_ACCESSORS_APP:
            return db in self.config.get_form_processing_dbs()
        else:
            return db == self.config.get_main_db()


class MonolithRouter(object):

    def allow_migrate(self, db, app_label, model=None, **hints):
        return app_label != PROXY_APP
