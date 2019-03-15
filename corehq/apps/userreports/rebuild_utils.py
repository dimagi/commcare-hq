from alembic.autogenerate import compare_metadata
import attr

from fluff.signals import get_migration_context, reformat_alembic_diffs


@attr.s
class TableDiffs(object):
    raw = attr.ib()
    formatted = attr.ib()


def get_table_diffs(engine, table_names, metadata):
    with engine.begin() as connection:
        migration_context = get_migration_context(connection, table_names)
        raw_diffs = compare_metadata(migration_context, metadata)
        diffs = reformat_alembic_diffs(raw_diffs)
    return TableDiffs(raw_diffs, diffs)
