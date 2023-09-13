import logging
from collections import defaultdict

import attr
from alembic.autogenerate import compare_metadata
from alembic.operations import Operations

from dimagi.utils.couch import get_redis_client

from .alembic_diffs import (
    DiffTypes,
    get_migration_context,
    get_tables_to_rebuild,
    reformat_alembic_diffs,
)
from .models import id_is_static

logger = logging.getLogger(__name__)


def get_redis_key_for_config(config):
    if id_is_static(config._id):
        rev = 'static'
    else:
        rev = config._rev
    return 'ucr_queue-{}:{}'.format(config._id, rev)


class DataSourceResumeHelper(object):

    def __init__(self, config):
        self.config = config
        self._client = get_redis_client().client.get_client()
        self._key = get_redis_key_for_config(config)

    def get_completed_iterations(self):
        return [
            value.decode('utf8').split(':')
            for value in self._client.lrange(self._key, 0, -1)
        ]

    def add_completed_iteration(self, domain, case_type_or_xmlns):
        if case_type_or_xmlns is None:
            case_type_or_xmlns = 'None'
        self._client.rpush(self._key, f"{domain}:{case_type_or_xmlns}".encode('utf8'))

    def clear_resume_info(self):
        self._client.delete(self._key)

    def has_resume_info(self):
        return self._client.exists(self._key)


@attr.s
class MigrateRebuildTables(object):
    migrate = attr.ib()
    rebuild = attr.ib()


def get_table_diffs(engine, table_names, metadata):
    with engine.begin() as connection:
        migration_context = get_migration_context(connection, table_names)
        raw_diffs = compare_metadata(migration_context, metadata)
        return [
            diff for diff in reformat_alembic_diffs(raw_diffs)
            if diff.table_name in table_names
        ]


def get_tables_rebuild_migrate(diffs):
    tables_to_rebuild = get_tables_to_rebuild(diffs)
    tables_to_migrate = get_tables_to_migrate(diffs)
    tables_to_ignore = get_tables_with_index_diff_only(diffs, index_column="inserted_at")
    tables_to_migrate -= tables_to_rebuild
    tables_to_migrate -= tables_to_ignore
    return MigrateRebuildTables(migrate=tables_to_migrate, rebuild=tables_to_rebuild)


def get_tables_with_index_diff_only(diffs, index_column):
    """Iterates `diffs` for tables where the only change is an index that's added to the `index_column`"""
    tables_to_ignore = set()
    valid_netto_index_diffs = _get_indexes_diffs_to_change(diffs)
    tables_with_index_change = {diff.table_name for diff in valid_netto_index_diffs}
    for table_name in tables_with_index_change:
        all_diffs_for_table = set(filter(lambda diff: diff.table_name == table_name, diffs))
        index_diffs_for_table = set(
            filter(
                lambda diff: diff.table_name == table_name,
                _filter_diffs(diffs, DiffTypes.INDEX_TYPES)
            )
        )
        # The following code needs context:
        # A `valid`` index is an index that's not being removed and added back. Those are there for some reason,
        # thus what we're doing is to filter those out and only look at diffs that will cause a netto change
        # to the table
        valid_index_diffs_for_table = set(
            filter(lambda diff: diff.table_name == table_name, valid_netto_index_diffs)
        )
        table_diffs_without_indexes = all_diffs_for_table - index_diffs_for_table
        netto_diffs_for_table = list(table_diffs_without_indexes.union(valid_index_diffs_for_table))
        if len(netto_diffs_for_table) > 1:
            continue
        _change_type, index = netto_diffs_for_table[0].raw
        columns = list(index.columns)
        if len(columns) > 1:
            # Not sure if/when this will happen?
            continue
        column = columns[0]
        if column.name == index_column:
            tables_to_ignore.add(table_name)
    return tables_to_ignore


def get_tables_to_migrate(diffs):
    return {diff.table_name for diff in _filter_diffs(
        diffs, DiffTypes.TYPES_FOR_MIGRATION
    )}


def _filter_diffs(diffs, types):
    return {
        diff
        for diff in diffs
        if diff.type in types
    }


def migrate_tables(engine, diffs):
    col_diffs = add_columns(engine, diffs)
    index_diffs = apply_index_changes(engine, diffs)

    changes_by_table = defaultdict(list)
    for diff in col_diffs | set(index_diffs):
        changes_by_table[diff.table_name].append(diff.to_dict())
    return changes_by_table


def add_columns(engine, diffs):
    with engine.begin() as conn:
        ctx = get_migration_context(conn)
        op = Operations(ctx)
        col_diffs = _filter_diffs(diffs, [DiffTypes.ADD_NULLABLE_COLUMN])
        for diff in col_diffs:
            col = diff.column
            table_name = col.table.name
            # the column has a reference to a table definition that already
            # has the column defined, so remove that and add the column
            col.table = None
            op.add_column(table_name, col)

    return col_diffs


def apply_index_changes(engine, diffs):
    """Note that this does not actually create the indexes. Indexes must be created
    manually by copying the log output.
    """
    index_diffs = _get_indexes_diffs_to_change(diffs)
    remove_indexes = [index.index for index in index_diffs if index.type == DiffTypes.REMOVE_INDEX]
    add_indexes = [index.index for index in index_diffs if index.type == DiffTypes.ADD_INDEX]

    for index in add_indexes:
        column_names = ', '.join(c.name for c in index.columns)
        logger.info(f'CREATE INDEX CONCURRENTLY "{index.name}" ON "{index.table.name}" ({column_names})')

    # don't remove indexes automatically because we want to be able to add them
    # concurrently without the code removing them
    for index in remove_indexes:
        logger.info(f'DROP INDEX CONCURRENTLY "{index.name}"')

    return index_diffs


def _get_indexes_diffs_to_change(diffs):
    # raw diffs come in as a list of (action, index)
    index_diffs = _filter_diffs(diffs, DiffTypes.INDEX_TYPES)
    index_diffs_by_table_and_col = defaultdict(list)

    for index_diff in index_diffs:
        index = index_diff.index

        column_names = tuple(index.columns.keys())
        index_diffs_by_table_and_col[(index.table.name, column_names)].append(index_diff)

    indexes_to_change = []

    for index_diffs in index_diffs_by_table_and_col.values():
        if len(index_diffs) == 1:
            indexes_to_change.append(index_diffs[0])
        else:
            # do nothing if alembic attempts to remove and add an index on the same column
            actions = [diff.type for diff in index_diffs]
            if (
                    len(actions) != 2
                    or DiffTypes.ADD_INDEX not in actions
                    or DiffTypes.REMOVE_INDEX not in actions
            ):
                table_name = index_diffs[0].table.name
                column_names = ', '.join(c.name for c in index_diffs[0].columns)
                logger.warning(f"There may be duplicate indexes on {table_name}, {column_names}")

    return indexes_to_change
