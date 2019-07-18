from __future__ import absolute_import
from __future__ import unicode_literals

from collections import defaultdict, namedtuple

import attr
from alembic.autogenerate import compare_metadata
from alembic.operations import Operations

from corehq.apps.userreports.exceptions import TableRebuildError
from corehq.apps.userreports.models import id_is_static
from corehq.util.soft_assert import soft_assert
from dimagi.utils.couch import get_redis_client
from fluff.signals import (
    get_migration_context,
    reformat_alembic_diffs,
    get_tables_to_rebuild,
    DiffTypes)
from six.moves import zip


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

    def get_completed_case_type_or_xmlns(self):
        return self._client.lrange(self._key, 0, -1)

    def add_completed_case_type_or_xmlns(self, case_type_or_xmlns):
        self._client.rpush(self._key, case_type_or_xmlns)

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
    tables_to_migrate -= tables_to_rebuild
    return MigrateRebuildTables(migrate=tables_to_migrate, rebuild=tables_to_rebuild)


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
    index_diffs = _get_indexes_diffs_to_change(diffs)
    remove_indexes = [index.index for index in index_diffs if index.type == DiffTypes.REMOVE_INDEX]
    add_indexes = [index.index for index in index_diffs if index.type == DiffTypes.ADD_INDEX]

    with engine.begin() as conn:
        for index in add_indexes:
            index.create(conn)

    # don't remove indexes automatically because we want to be able to add them
    # concurrently without the code removing them
    _assert = soft_assert(to="@".join(["jemord", "dimagi.com"]))
    for index in remove_indexes:
        _assert(False, "Index {} can be removed".format(index.name))

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
                raise TableRebuildError("Unexpected diffs")

    return indexes_to_change
