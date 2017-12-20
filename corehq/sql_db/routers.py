from __future__ import absolute_import
from django.conf import settings

from corehq.sql_db.connections import connection_manager, ICDS_UCR_ENGINE_ID
from .config import partition_config

PROXY_APP = 'sql_proxy_accessors'
FORM_PROCESSOR_APP = 'form_processor'
SQL_ACCESSORS_APP = 'sql_accessors'
ICDS_REPORTS_APP = 'icds_reports'
ICDS_MODEL = 'icds_model'
SCHEDULING_PARTITIONED_APP = 'scheduling_partitioned'
WAREHOUSE_APP = 'warehouse'


class PartitionRouter(object):

    def db_for_read(self, model, **hints):
        return db_for_read_write(model, write=False)

    def db_for_write(self, model, **hints):
        return db_for_read_write(model, write=True)

    def allow_migrate(self, db, app_label, model=None, **hints):
        return allow_migrate(db, app_label)

    def allow_relation(self, obj1, obj2, **hints):
        from corehq.sql_db.models import PartitionedModel
        obj1_partitioned = isinstance(obj1, PartitionedModel)
        obj2_partitioned = isinstance(obj2, PartitionedModel)
        if obj1_partitioned and obj2_partitioned:
            return obj1.db == obj2.db
        elif not obj1_partitioned and not obj2_partitioned:
            return True
        return False


class MonolithRouter(object):

    def allow_migrate(self, db, app_label, model=None, **hints):
        return app_label != PROXY_APP


def allow_migrate(db, app_label):
    if app_label == ICDS_REPORTS_APP:
        try:
            return db == connection_manager.get_django_db_alias(ICDS_UCR_ENGINE_ID)
        except KeyError:
            return False

    if not settings.USE_PARTITIONED_DATABASE:
        return app_label != PROXY_APP

    if app_label == PROXY_APP:
        return db == partition_config.get_proxy_db()
    elif app_label in (FORM_PROCESSOR_APP, SCHEDULING_PARTITIONED_APP):
        return (
            db == partition_config.get_proxy_db() or
            db in partition_config.get_form_processing_dbs()
        )
    elif app_label == SQL_ACCESSORS_APP:
        return db in partition_config.get_form_processing_dbs()
    elif app_label == WAREHOUSE_APP:
        return hasattr(settings, "WAREHOUSE_DATABASE_ALIAS") and db == settings.WAREHOUSE_DATABASE_ALIAS
    else:
        return db == partition_config.get_main_db()


def db_for_read_write(model, write=True):
    """
    :param model: Django model being queried
    :param write: Default to True since the DB for writes can also handle reads
    :return: Django DB alias to use for query
    """
    if not settings.USE_PARTITIONED_DATABASE:
        return 'default'

    app_label = model._meta.app_label
    if app_label == FORM_PROCESSOR_APP:
        return partition_config.get_proxy_db()
    elif app_label == WAREHOUSE_APP:
        error_msg = 'Cannot read/write to warehouse db without warehouse database defined'
        assert hasattr(settings, "WAREHOUSE_DATABASE_ALIAS"), error_msg
        return settings.WAREHOUSE_DATABASE_ALIAS
    elif app_label == ICDS_MODEL:
        engine_id = ICDS_UCR_ENGINE_ID
        if not write:
            engine_id = connection_manager.get_load_balanced_read_engine_id(ICDS_UCR_ENGINE_ID)
        return connection_manager.get_django_db_alias(engine_id)
    else:
        return partition_config.get_main_db()
