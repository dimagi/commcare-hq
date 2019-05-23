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


class TableDiffs(object):
    def __init__(self, raw=None, formatted=None):
        self.raw = raw or []
        self.formatted = formatted or []
        self.validate()

    def validate(self):
        if len(self.raw) != len(self.formatted):
            raise ValueError("Expecting 'raw' and 'formatted' to be of the same length")

    def filter(self, table_names):
        self.validate()
        new = TableDiffs()
        for raw, formatted in zip(self.raw, self.formatted):
            if formatted.table_name in table_names:
                new.raw.append(raw)
                new.formatted.append(formatted)
        new.validate()
        return new


@attr.s
class MigrateRebuildTables(object):
    migrate = attr.ib()
    rebuild = attr.ib()


SimpleIndexDiff = namedtuple('SimpleIndexDiff', 'action index')


def get_table_diffs(engine, table_names, metadata):
    with engine.begin() as connection:
        migration_context = get_migration_context(connection, table_names)
        raw_diffs = compare_metadata(migration_context, metadata)
        flattened_raw, diffs = reformat_alembic_diffs(raw_diffs)
    return TableDiffs(raw=flattened_raw, formatted=diffs)


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
    column_changes = add_columns(engine, raw_diffs, table_names)
    index_changes = apply_index_changes(engine, raw_diffs, table_names)

    for table, changes in index_changes.items():
        if table in column_changes:
            column_changes[table].extend(changes)
        else:
            column_changes[table] = changes
    return column_changes


def add_columns(engine, raw_diffs, table_names):
    changes = defaultdict(list)
    with engine.begin() as conn:
        ctx = get_migration_context(conn, table_names)
        op = Operations(ctx)
        columns = _get_columns_to_add(raw_diffs, table_names)
        for col in columns:
            table_name = col.table.name
            # the column has a reference to a table definition that already
            # has the column defined, so remove that and add the column
            col.table = None
            changes[table_name].append({
                'type': DiffTypes.ADD_COLUMN,
                'item_name': col.name
            })
            op.add_column(table_name, col)

    return dict(changes)


def apply_index_changes(engine, raw_diffs, table_names):
    changes = defaultdict(list)
    indexes = _get_indexes_to_change(raw_diffs, table_names)
    remove_indexes = [index.index for index in indexes if index.action == DiffTypes.REMOVE_INDEX]
    add_indexes = [index.index for index in indexes if index.action == DiffTypes.ADD_INDEX]

    with engine.begin() as conn:
        for index in add_indexes:
            changes[index.table.name].append({
                'type': DiffTypes.ADD_INDEX,
                'item_name': index.name
            })
            index.create(conn)

    # don't remove indexes automatically because we want to be able to add them
    # concurrently without the code removing them
    _assert = soft_assert(to="@".join(["jemord", "dimagi.com"]))
    for index in remove_indexes:
        _assert(False, "Index {} can be removed".format(index.name))

    return dict(changes)


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
            # do nothing if alembic attempts to remove and add an index on the same column
            actions = [diff.action for diff in index_diffs]
            if (
                    len(actions) != 2
                    or DiffTypes.ADD_INDEX not in actions
                    or DiffTypes.REMOVE_INDEX not in actions
            ):
                raise TableRebuildError("Unexpected diffs")

    return indexes_to_change
