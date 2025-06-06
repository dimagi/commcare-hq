from collections import defaultdict

from couchdbkit import ResourceNotFound

from pillowtop.logger import pillow_logging

from corehq.sql_db.connections import connection_manager
from corehq.util.soft_assert import soft_assert

from .exceptions import StaleRebuildError, TableRebuildError
from .rebuild import (
    get_table_diffs,
    get_tables_rebuild_migrate,
    migrate_tables,
)
from .sql import get_metadata
from .tasks import rebuild_indicators


def _is_datasource_active(adapter):
    """
    Tries to fetch a fresh copy of datasource from couchdb to know whether it is active.
    If it does not exist then it assumed to be deactivated
    """
    try:
        config_id = adapter.config._id
        config = adapter.config.get(config_id)
    except ResourceNotFound:
        return False
    return not config.is_deactivated


def rebuild_sql_tables(adapters):

    def _notify_rebuild(msg, obj):
        assert_ = soft_assert(notify_admins=True)
        assert_(False, msg, obj)

    tables_by_engine = defaultdict(dict)
    all_adapters = []
    for adapter in adapters:
        if getattr(adapter, 'all_adapters', None):
            all_adapters.extend(adapter.all_adapters)
        else:
            all_adapters.append(adapter)
    for adapter in all_adapters:
        if _is_datasource_active(adapter):
            tables_by_engine[adapter.engine_id][adapter.get_table().name] = adapter
        else:
            pillow_logging.info(
                f"""[rebuild] Tried to rebuild deactivated data source.
                Id - {adapter.config._id}
                Domain {adapter.config.domain}.
                Skipping."""
            )
    for engine_id, table_map in tables_by_engine.items():
        table_names = list(table_map)
        engine = connection_manager.get_engine(engine_id)

        diffs = get_table_diffs(engine, table_names, get_metadata(engine_id))

        tables_to_act_on = get_tables_rebuild_migrate(diffs)
        for table_name in tables_to_act_on.rebuild:
            sql_adapter = table_map[table_name]
            pillow_logging.info(
                "[rebuild] Rebuilding table: %s, from config %s at rev %s",
                table_name, sql_adapter.config._id, sql_adapter.config._rev
            )
            pillow_logging.info("[rebuild] Using config: %r", sql_adapter.config)
            pillow_logging.info("[rebuild] sqlalchemy metadata: %r", get_metadata(engine_id).tables[table_name])
            pillow_logging.info("[rebuild] sqlalchemy table: %r", sql_adapter.get_table())
            table_diffs = [diff for diff in diffs if diff.table_name == table_name]
            if not sql_adapter.config.is_static:
                try:
                    rebuild_table(sql_adapter, table_diffs)
                except TableRebuildError as e:
                    _notify_rebuild(str(e), sql_adapter.config.to_json())
            else:
                rebuild_table(sql_adapter, table_diffs)

        migrate_tables_with_logging(engine, diffs, tables_to_act_on.migrate, table_map)


def migrate_tables_with_logging(engine, diffs, table_names, adapters_by_table):
    migration_diffs = [diff for diff in diffs if diff.table_name in table_names]
    for table in table_names:
        adapter = adapters_by_table[table]
        pillow_logging.info("[rebuild] Using config: %r", adapter.config)
        pillow_logging.info("[rebuild] sqlalchemy metadata: %r", get_metadata(adapter.engine_id).tables[table])
        pillow_logging.info("[rebuild] sqlalchemy table: %r", adapter.get_table())
    changes = migrate_tables(engine, migration_diffs)
    for table, diffs in changes.items():
        adapter = adapters_by_table[table]
        pillow_logging.info(
            "[rebuild] Migrating table: %s, from config %s at rev %s",
            table, adapter.config._id, adapter.config._rev
        )
        adapter.log_table_migrate(source='pillowtop', diffs=diffs)


def rebuild_table(adapter, diffs=None):
    config = adapter.config
    if not config.is_static:
        latest_rev = config.get_db().get_rev(config._id)
        if config._rev != latest_rev:
            raise StaleRebuildError('Tried to rebuild a stale table ({})! Ignoring...'.format(config))

    diff_dicts = [diff.to_dict() for diff in diffs]
    if config.disable_destructive_rebuild and adapter.table_exists:
        adapter.log_table_rebuild_skipped(source='pillowtop', diffs=diff_dicts)
        return

    rebuild_indicators.delay(
        adapter.config.get_id,
        source='pillowtop',
        engine_id=adapter.engine_id,
        diffs=diff_dicts,
        domain=config.domain,
    )
