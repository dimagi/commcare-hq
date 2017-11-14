from __future__ import absolute_import
from django.conf import settings

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
        return db_for_read_write(model)

    def db_for_write(self, model, **hints):
        return db_for_read_write(model)

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
        return hasattr(settings, "ICDS_UCR_DATABASE_ALIAS") and db == settings.ICDS_UCR_DATABASE_ALIAS

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


def db_for_read_write(model):
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
        assert hasattr(settings, "ICDS_UCR_TEST_DATABASE_ALIAS")
        return settings.ICDS_UCR_TEST_DATABASE_ALIAS

    else:
        return partition_config.get_main_db()
