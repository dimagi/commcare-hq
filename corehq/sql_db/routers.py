from django.conf import settings
from django.db import DEFAULT_DB_ALIAS, connections

from corehq.sql_db.connections import (
    AAA_DB_ENGINE_ID,
    ICDS_UCR_CITUS_ENGINE_ID,
    connection_manager,
    get_aaa_db_alias,
    get_icds_ucr_citus_db_alias,
)
from corehq.sql_db.util import select_db_for_read

from .config import plproxy_config

HINT_INSTANCE = 'instance'
HINT_PARTITION_VALUE = 'partition_value'
HINT_PLPROXY = 'plproxy'
HINT_USING = 'using'
ALL_HINTS = {HINT_INSTANCE, HINT_PARTITION_VALUE, HINT_PLPROXY, HINT_USING}

PROXY_APP = 'sql_proxy_accessors'
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
            return obj1.db == obj2.db
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
    if app_label == ICDS_REPORTS_APP:
        db_alias = get_icds_ucr_citus_db_alias()
        return bool(db_alias and db_alias == db)
    elif app_label == AAA_APP:
        db_alias = get_aaa_db_alias()
        return bool(db_alias and db_alias == db)
    elif app_label == SYNCLOGS_APP:
        return db == settings.SYNCLOGS_SQL_DB_ALIAS

    if not settings.USE_PARTITIONED_DATABASE:
        return app_label != PROXY_APP and db in (DEFAULT_DB_ALIAS, None)

    if app_label == PROXY_APP:
        return db == plproxy_config.proxy_db
    elif app_label == BLOB_DB_APP and db == DEFAULT_DB_ALIAS:
        return True
    elif app_label == BLOB_DB_APP and model_name == 'blobexpiration':
        return False
    elif app_label in (FORM_PROCESSOR_APP, SCHEDULING_PARTITIONED_APP, BLOB_DB_APP):
        return (
            db == plproxy_config.proxy_db or
            db in plproxy_config.form_processing_dbs
        )
    elif app_label == SQL_ACCESSORS_APP:
        return db in plproxy_config.form_processing_dbs
    else:
        return db == DEFAULT_DB_ALIAS


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
            return get_db_for_plproxy_cluster(model, hints)
        return DEFAULT_DB_ALIAS
    if app_label in (FORM_PROCESSOR_APP, SCHEDULING_PARTITIONED_APP):
        return get_db_for_plproxy_cluster(model, hints)
    else:
        default_db = DEFAULT_DB_ALIAS
        if not write:
            return get_load_balanced_app_db(app_label, default_db)
        return default_db


def get_db_for_plproxy_cluster(model, hints):
    from corehq.sql_db.util import get_db_alias_for_partitioned_doc, get_db_aliases_for_partitioned_query

    if not hints:
        raise Exception(f'Routing for partitioned models requires a hint. Use one of {ALL_HINTS}')

    if len(set(hints) & ALL_HINTS) > 1:
        raise Exception(f'Unable to perform routing, multiple hints provided: {hints}')

    if HINT_INSTANCE in hints:
        partition_value = getattr(hints[HINT_INSTANCE], 'partition_value', None)
        if partition_value is not None:
            return get_db_alias_for_partitioned_doc(partition_value)
    if hints.get(HINT_PLPROXY):
        return plproxy_config.proxy_db
    if HINT_USING in hints:
        db = hints[HINT_USING]
        assert db in get_db_aliases_for_partitioned_query()
        return db
    if HINT_PARTITION_VALUE in hints:
        return get_db_alias_for_partitioned_doc(hints[HINT_PARTITION_VALUE])

    raise Exception(f'Unable to route query for {model}. No matching hints. Use one of {ALL_HINTS}')


def get_load_balanced_app_db(app_name: str, default: str) -> str:
    read_dbs = settings.LOAD_BALANCED_APPS.get(app_name)
    return select_db_for_read(read_dbs) or default
