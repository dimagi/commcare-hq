from alembic.autogenerate import compare_metadata
import attr

from fluff.signals import (
    get_migration_context,
    reformat_alembic_diffs,
    get_tables_to_rebuild,
    get_tables_to_migrate
)


@attr.s
class TableDiffs(object):
    raw = attr.ib()
    formatted = attr.ib()


@attr.s
class MigrateRebuildTables(object):
    migrate = attr.ib()
    rebuild = attr.ib()


def get_table_diffs(engine, table_names, metadata):
    with engine.begin() as connection:
        migration_context = get_migration_context(connection, table_names)
        raw_diffs = compare_metadata(migration_context, metadata)
        diffs = reformat_alembic_diffs(raw_diffs)
    return TableDiffs(raw=raw_diffs, formatted=diffs)


def get_tables_rebulid_migrate(diffs, table_names):
    tables_to_rebuild = get_tables_to_rebuild(diffs.formatted, table_names)
    tables_to_migrate = get_tables_to_migrate(diffs.formatted, table_names)
    tables_to_migrate -= tables_to_rebuild
    return MigrateRebuildTables(migrate=tables_to_migrate, rebuild=tables_to_rebuild)
