from .config import PartitionConfig

PROXY_APP = 'sql_proxy_accessors'
FORM_PROCESSOR_APP = 'form_processor'
SQL_ACCESSORS_APP = 'sql_accessors'


class PartitionRouter(object):

    def allow_migrate(self, db, model):
        app_label = model._meta.app_label
        return allow_migrate(db, app_label)


class MonolithRouter(object):

    def allow_migrate(self, db, app_label, model=None, **hints):
        return app_label != PROXY_APP


def allow_migrate(db, app_label):
    partition_config = PartitionConfig()
    if app_label == PROXY_APP:
        return db == partition_config.get_proxy_db()
    elif app_label == FORM_PROCESSOR_APP:
        return (
            db == partition_config.get_proxy_db() or
            db in partition_config.get_form_processing_dbs()
        )
    elif app_label == SQL_ACCESSORS_APP:
        return db in partition_config.get_form_processing_dbs()
    else:
        return db == partition_config.get_main_db()
