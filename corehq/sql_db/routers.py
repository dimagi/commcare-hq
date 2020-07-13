import os

from contextlib import ContextDecorator
from threading import local

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS

from corehq.sql_db.config import plproxy_standby_config
from corehq.sql_db.connections import (
    AAA_DB_ENGINE_ID,
    ICDS_UCR_CITUS_ENGINE_ID,
    connection_manager,
    get_aaa_db_alias,
    get_icds_ucr_citus_db_alias,
)
from corehq.sql_db.util import select_db_for_read, select_plproxy_db_for_read

from .config import plproxy_config

READ_FROM_PLPROXY_STANDBYS = 'READ_FROM_PLPROXY_STANDBYS'

HINT_INSTANCE = 'instance'
HINT_PARTITION_VALUE = 'partition_value'
HINT_PLPROXY = 'plproxy'
HINT_USING = 'using'
ALL_HINTS = {HINT_INSTANCE, HINT_PARTITION_VALUE, HINT_PLPROXY, HINT_USING}

PROXY_APP = 'sql_proxy_accessors'
PROXY_STANDBY_APP = 'sql_proxy_standby_accessors'
FORM_PROCESSOR_APP = 'form_processor'
BLOB_DB_APP = 'blobs'
SQL_ACCESSORS_APP = 'sql_accessors'
ICDS_REPORTS_APP = 'icds_reports'
SCHEDULING_PARTITIONED_APP = 'scheduling_partitioned'
SYNCLOGS_APP = 'phone'
AAA_APP = 'aaa'


class MultiDBRouter(object):

    def db_for_read(self, model, **hints):
        return db_for_read_write(model, write=False, hints=hints)

    def db_for_write(self, model, **hints):
        return db_for_read_write(model, write=True, hints=hints)

    def allow_migrate(self, db, app_label, model=None, model_name=None, **hints):
        return allow_migrate(db, app_label, model_name)

    def allow_relation(self, obj1, obj2, **hints):
        from corehq.sql_db.models import PartitionedModel
        obj1_partitioned = isinstance(obj1, PartitionedModel)
        obj2_partitioned = isinstance(obj2, PartitionedModel)
        if obj1_partitioned and obj2_partitioned:
            if 'partition_value' not in obj2.__dict__:
                # skip this check when the model is first being initialized
                return True
            else:
                return obj1.partition_value == obj2.partition_value
        elif not obj1_partitioned and not obj2_partitioned:
            app1, app2 = obj1._meta.app_label, obj2._meta.app_label
            if app1 == SYNCLOGS_APP:
                # this app lives in its own database
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
    if db and not settings.DATABASES[db].get('MIGRATE', True):
        return False

    if app_label == ICDS_REPORTS_APP:
        db_alias = get_icds_ucr_citus_db_alias()
        return bool(db_alias and db_alias == db)
    elif app_label == AAA_APP:
        db_alias = get_aaa_db_alias()
        return bool(db_alias and db_alias == db)
    elif app_label == SYNCLOGS_APP:
        return db == settings.SYNCLOGS_SQL_DB_ALIAS

    if not settings.USE_PARTITIONED_DATABASE:
        return app_label not in (PROXY_APP, PROXY_STANDBY_APP) and db in (DEFAULT_DB_ALIAS, None)

    if app_label == PROXY_APP:
        return (
            db == plproxy_config.proxy_db
            or bool(plproxy_standby_config and db == plproxy_standby_config.proxy_db)
        )
    if app_label == PROXY_STANDBY_APP:
        return bool(plproxy_standby_config and db == plproxy_standby_config.proxy_db)
    elif app_label == BLOB_DB_APP and db == DEFAULT_DB_ALIAS:
        return True
    elif app_label == BLOB_DB_APP and model_name == 'blobexpiration':
        return False
    elif app_label in (FORM_PROCESSOR_APP, SCHEDULING_PARTITIONED_APP, BLOB_DB_APP):
        return (
            db == plproxy_config.proxy_db
            or db in plproxy_config.form_processing_dbs
            or bool(plproxy_standby_config and db == plproxy_standby_config.proxy_db)
        )
    elif app_label == SQL_ACCESSORS_APP:
        return db in plproxy_config.form_processing_dbs
    else:
        return db in (DEFAULT_DB_ALIAS, None)


def db_for_read_write(model, write=True, hints=None):
    """
    :param model: Django model being queried
    :param write: Default to True since the DB for writes can also handle reads
    :return: Django DB alias to use for query
    """
    hints = hints or {}
    app_label = model._meta.app_label

    if app_label == SYNCLOGS_APP:
        return settings.SYNCLOGS_SQL_DB_ALIAS
    elif app_label == ICDS_REPORTS_APP:
        return connection_manager.get_django_db_alias(ICDS_UCR_CITUS_ENGINE_ID)
    elif app_label == AAA_APP:
        engine_id = AAA_DB_ENGINE_ID
        if not write:
            return connection_manager.get_load_balanced_read_db_alias(AAA_DB_ENGINE_ID)
        return connection_manager.get_django_db_alias(engine_id)

    if not settings.USE_PARTITIONED_DATABASE:
        return DEFAULT_DB_ALIAS

    if app_label == BLOB_DB_APP:
        if hasattr(model, 'partition_attr'):
            return get_read_write_db_for_partitioned_model(model, hints, write)
        return DEFAULT_DB_ALIAS
    if app_label in (FORM_PROCESSOR_APP, SCHEDULING_PARTITIONED_APP):
        return get_read_write_db_for_partitioned_model(model, hints, write)
    else:
        default_db = DEFAULT_DB_ALIAS
        if not write:
            return get_load_balanced_app_db(app_label, default_db)
        return default_db


def get_read_write_db_for_partitioned_model(model, hints, for_write):
    db = get_db_for_partitioned_model(model, hints)
    if for_write or not allow_read_from_plproxy_standby():
        return db
    return select_plproxy_db_for_read(db)


def get_db_for_partitioned_model(model, hints):
    from corehq.sql_db.util import get_db_alias_for_partitioned_doc, get_db_aliases_for_partitioned_query

    if not hints:
        raise Exception(f'Routing for partitioned models requires a hint. Use one of {ALL_HINTS}')

    if len(set(hints) & ALL_HINTS) > 1:
        raise Exception(f'Unable to perform routing, multiple hints provided: {hints}')

    if HINT_INSTANCE in hints:
        instance = hints[HINT_INSTANCE]
        if instance._state.db is not None:
            return instance._state.db
        partition_value = getattr(instance, 'partition_value', None)
        if partition_value is not None:
            return get_db_alias_for_partitioned_doc(partition_value)
    if hints.get(HINT_PLPROXY):
        return plproxy_config.proxy_db
    if HINT_USING in hints:
        db = hints[HINT_USING]
        assert db in get_db_aliases_for_partitioned_query(), "{} not in {}".format(
            db, ", ".join(get_db_aliases_for_partitioned_query()))
        return db
    if HINT_PARTITION_VALUE in hints:
        return get_db_alias_for_partitioned_doc(hints[HINT_PARTITION_VALUE])

    raise Exception(f'Unable to route query for {model}. No matching hints. Use one of {ALL_HINTS}')


def get_load_balanced_app_db(app_name: str, default: str) -> str:
    read_dbs = settings.LOAD_BALANCED_APPS.get(app_name)
    return select_db_for_read(read_dbs) or default


_thread_locals = local()


def allow_read_from_plproxy_standby():
    return os.environ.get(READ_FROM_PLPROXY_STANDBYS) or getattr(_thread_locals, READ_FROM_PLPROXY_STANDBYS, False)


class read_from_plproxy_standbys(ContextDecorator):
    def __enter__(self):
        setattr(_thread_locals, READ_FROM_PLPROXY_STANDBYS, True)

    def __exit__(self, exc_type, exc_val, exc_tb):
        setattr(_thread_locals, READ_FROM_PLPROXY_STANDBYS, False)
