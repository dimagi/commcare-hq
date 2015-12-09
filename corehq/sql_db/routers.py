from django.conf import settings

from .config import PartitionConfig

PROXY_APP = 'sql_proxy_accessors'
FORM_PROCESSOR_APP = 'form_processor'
SQL_ACCESSORS_APP = 'sql_accessors'


class PartitionRouter(object):

    def db_for_read(self, model, **hints):
        return db_for_read_write(model)

    def db_for_write(self, model, **hints):
        return db_for_read_write(model)

    def allow_migrate(self, db, model):
        app_label = model._meta.app_label
        return allow_migrate(db, app_label)


class MonolithRouter(object):

    def allow_migrate(self, db, app_label, model=None, **hints):
        return app_label != PROXY_APP


def allow_migrate(db, app_label):
    if not settings.USE_PARTITIONED_DATABASE:
        return app_label != PROXY_APP

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


def db_for_read_write(model):
    if not settings.USE_PARTITIONED_DATABASE:
        return 'default'

    app_label = model._meta.app_label
    config = PartitionConfig()
    if app_label == FORM_PROCESSOR_APP:
        return config.get_proxy_db()
    else:
        return config.get_main_db()
