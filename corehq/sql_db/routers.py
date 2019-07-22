from __future__ import absolute_import
from __future__ import unicode_literals

from contextlib import contextmanager
import threading

from django.conf import settings
from django.db import connections

from corehq.sql_db.connections import (
    AAA_DB_ENGINE_ID,
    ICDS_UCR_ENGINE_ID,
    ICDS_UCR_CITUS_ENGINE_ID,
    connection_manager,
    get_aaa_db_alias,
    get_icds_ucr_db_alias,
    get_icds_ucr_citus_db_alias)

from .config import partition_config

PROXY_APP = 'sql_proxy_accessors'
FORM_PROCESSOR_APP = 'form_processor'
BLOB_DB_APP = 'blobs'
SQL_ACCESSORS_APP = 'sql_accessors'
ICDS_REPORTS_APP = 'icds_reports'
SCHEDULING_PARTITIONED_APP = 'scheduling_partitioned'
WAREHOUSE_APP = 'warehouse'
SYNCLOGS_APP = 'phone'
AAA_APP = 'aaa'

_thread_local = threading.local()


class MultiDBRouter(object):

    def db_for_read(self, model, **hints):
        return db_for_read_write(model, write=False)

    def db_for_write(self, model, **hints):
        return db_for_read_write(model, write=True)

    def allow_migrate(self, db, app_label, model=None, model_name=None, **hints):
        return allow_migrate(db, app_label, model_name)

    def allow_relation(self, obj1, obj2, **hints):
        from corehq.sql_db.models import PartitionedModel
        obj1_partitioned = isinstance(obj1, PartitionedModel)
        obj2_partitioned = isinstance(obj2, PartitionedModel)
        if obj1_partitioned and obj2_partitioned:
            return obj1.db == obj2.db
        elif not obj1_partitioned and not obj2_partitioned:
            app1, app2 = obj1._meta.app_label, obj2._meta.app_label
            if app1 in (SYNCLOGS_APP, WAREHOUSE_APP):
                # these apps live in their own databases
                return app1 == app2
            return True
        return False


def allow_migrate(db, app_label, model_name=None):
    """
    Return ``True`` if a app's migrations should be applied to the specified database otherwise
    return ``False``.

    Note: returning ``None`` is tantamount to returning ``True``

    :return: Must return a boolean value, not None.
    """
    if app_label == ICDS_REPORTS_APP:
        db_aliases = [get_icds_ucr_db_alias(), get_icds_ucr_citus_db_alias()]
        return db in db_aliases
    elif app_label == AAA_APP:
        db_alias = get_aaa_db_alias()
        return bool(db_alias and db_alias == db)
    elif app_label == SYNCLOGS_APP:
        return db == settings.SYNCLOGS_SQL_DB_ALIAS
    elif app_label == WAREHOUSE_APP:
        return db == settings.WAREHOUSE_DATABASE_ALIAS

    if not settings.USE_PARTITIONED_DATABASE:
        return app_label != PROXY_APP and db in ('default', None)

    if app_label == PROXY_APP:
        return db == partition_config.get_proxy_db()
    elif app_label == BLOB_DB_APP and db == 'default':
        return True
    elif app_label == BLOB_DB_APP and model_name == 'blobexpiration':
        return False
    elif app_label in (FORM_PROCESSOR_APP, SCHEDULING_PARTITIONED_APP, BLOB_DB_APP):
        return (
            db == partition_config.get_proxy_db() or
            db in partition_config.get_form_processing_dbs()
        )
    elif app_label == SQL_ACCESSORS_APP:
        return db in partition_config.get_form_processing_dbs()
    else:
        return db == partition_config.get_main_db()


def db_for_read_write(model, write=True):
    """
    :param model: Django model being queried
    :param write: Default to True since the DB for writes can also handle reads
    :return: Django DB alias to use for query
    """
    app_label = model._meta.app_label

    if app_label == WAREHOUSE_APP:
        return settings.WAREHOUSE_DATABASE_ALIAS
    elif app_label == SYNCLOGS_APP:
        return settings.SYNCLOGS_SQL_DB_ALIAS
    elif app_label == ICDS_REPORTS_APP:
        if forced_citus():
            engine_id = ICDS_UCR_CITUS_ENGINE_ID
        else:
            engine_id = ICDS_UCR_ENGINE_ID
            if not write:
                engine_id = connection_manager.get_load_balanced_read_db_alias(ICDS_UCR_ENGINE_ID)
        return connection_manager.get_django_db_alias(engine_id)
    elif app_label == AAA_APP:
        engine_id = AAA_DB_ENGINE_ID
        if not write:
            engine_id = connection_manager.get_load_balanced_read_db_alias(AAA_DB_ENGINE_ID)
        return connection_manager.get_django_db_alias(engine_id)

    if not settings.USE_PARTITIONED_DATABASE:
        return 'default'

    if app_label == BLOB_DB_APP:
        if hasattr(model, 'partition_attr'):
            return partition_config.get_proxy_db()
        return 'default'
    if app_label == FORM_PROCESSOR_APP:
        return partition_config.get_proxy_db()
    else:
        default_db = partition_config.get_main_db()
        if not write:
            return connection_manager.get_load_balanced_read_db_alias(app_label, default_db)
        return default_db


def get_cursor(model):
    db = db_for_read_write(model)
    return connections[db].cursor()


def force_citus_engine(force=False):
    if force:
        _thread_local.force_citus = True
    yield
    _thread_local.force_citus = False


def forced_citus():
    return getattr(_thread_local, 'force_citus', False)
