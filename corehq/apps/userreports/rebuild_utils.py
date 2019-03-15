from collections import defaultdict, namedtuple

import attr
from alembic.autogenerate import compare_metadata
from alembic.operations import Operations

from corehq.apps.userreports.exceptions import TableRebuildError
from corehq.util.soft_assert import soft_assert
from fluff.signals import (
    get_migration_context,
    reformat_alembic_diffs,
    get_tables_to_rebuild,
    DiffTypes)


@attr.s
class TableDiffs(object):
    raw = attr.ib()
    formatted = attr.ib()


@attr.s
class MigrateRebuildTables(object):
    migrate = attr.ib()
    rebuild = attr.ib()


SimpleIndexDiff = namedtuple('SimpleIndexDiff', 'action index')


def get_table_diffs(engine, table_names, metadata):
    with engine.begin() as connection:
        migration_context = get_migration_context(connection, table_names)
        raw_diffs = compare_metadata(migration_context, metadata)
        diffs = reformat_alembic_diffs(raw_diffs)
    return TableDiffs(raw=raw_diffs, formatted=diffs)


def get_tables_rebuild_migrate(diffs, table_names):
    tables_to_rebuild = get_tables_to_rebuild(diffs.formatted, table_names)
    tables_to_migrate = get_tables_to_migrate(diffs.formatted, table_names)
    tables_to_migrate -= tables_to_rebuild
    return MigrateRebuildTables(migrate=tables_to_migrate, rebuild=tables_to_rebuild)


def get_tables_to_migrate(diffs, table_names):
    tables_with_indexes = get_tables_with_index_changes(diffs, table_names)
    tables_with_added_columns = get_tables_with_added_nullable_columns(diffs, table_names)
    return tables_with_indexes | tables_with_added_columns


def get_tables_with_index_changes(diffs, table_names):
    return {
        diff.table_name
        for diff in diffs
        if diff.table_name in table_names and diff.type in DiffTypes.INDEX_TYPES
    }


def get_tables_with_added_nullable_columns(diffs, table_names):
    return {
        diff.table_name
        for diff in diffs
        if (
            diff.table_name in table_names
            and diff.type == DiffTypes.ADD_NULLABLE_COLUMN
        )
    }


def migrate_tables(engine, raw_diffs, table_names):
    add_columns(engine, raw_diffs, table_names)
    apply_index_changes(engine, raw_diffs, table_names)


def add_columns(engine, raw_diffs, table_names):
    with engine.begin() as conn:
        ctx = get_migration_context(conn, table_names)
        op = Operations(ctx)
        columns = _get_columns_to_add(raw_diffs, table_names)

        for col in columns:
            table_name = col.table.name
            # the column has a reference to a table definition that already
            # has the column defined, so remove that and add the column
            col.table = None
            op.add_column(table_name, col)


def apply_index_changes(engine, raw_diffs, table_names):
    indexes = _get_indexes_to_change(raw_diffs, table_names)
    remove_indexes = [index.index for index in indexes if index.action == DiffTypes.REMOVE_INDEX]
    add_indexes = [index.index for index in indexes if index.action == DiffTypes.ADD_INDEX]

    with engine.begin() as conn:
        for index in add_indexes:
            index.create(conn)

    # don't remove indexes automatically because we want to be able to add them
    # concurrently without the code removing them
    _assert = soft_assert(to="@".join(["jemord", "dimagi.com"]))
    for index in remove_indexes:
        _assert(False, "Index {} can be removed".format(index.name))


def _get_columns_to_add(raw_diffs, table_names):
    # raw diffs come in as a list of (action, index)
    return [
        diff[3]
        for diff in raw_diffs
        if diff[0] in DiffTypes.ADD_COLUMN and diff[3].nullable is True
    ]


def _get_indexes_to_change(raw_diffs, table_names):
    # raw diffs come in as a list of (action, index)
    index_diffs = [
        SimpleIndexDiff(action=diff[0], index=diff[1])
        for diff in raw_diffs if diff[0] in DiffTypes.INDEX_TYPES
    ]
    index_diffs_by_table_and_col = defaultdict(list)

    for index_diff in index_diffs:
        index = index_diff.index
        if index.table.name not in table_names:
            continue

        column_names = tuple(index.columns.keys())
        index_diffs_by_table_and_col[(index.table.name, column_names)].append(index_diff)

    indexes_to_change = []

    for index_diffs in index_diffs_by_table_and_col.values():
        if len(index_diffs) == 1:
            indexes_to_change.append(index_diffs[0])
        else:
            # tests when alembic tries to remove/add the same index
            actions = [diff.action for diff in index_diffs]
            if (
                    len(actions) != 2
                    or DiffTypes.ADD_INDEX not in actions
                    or DiffTypes.REMOVE_INDEX not in actions
            ):
                raise TableRebuildError("Unexpected diffs")

    return indexes_to_change
