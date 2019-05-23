from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
from functools import partial

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import attr
from django.conf import settings
from django.db import DEFAULT_DB_ALIAS
from django.dispatch import Signal

from corehq.sql_db.connections import connection_manager
from fluff.util import metadata as fluff_metadata

logger = logging.getLogger('fluff')

BACKEND_COUCH = 'COUCH'
BACKEND_SQL = 'SQL'

indicator_document_updated = Signal(providing_args=["doc", "diff", "backend"])


class DiffTypes(object):
    ADD_TABLE = 'add_table'
    REMOVE_TABLE = 'remove_table'
    TABLE_TYPES = (ADD_TABLE, REMOVE_TABLE)

    ADD_COLUMN = 'add_column'
    REMOVE_COLUMN = 'remove_column'
    COLUMN_TYPES = (ADD_COLUMN, REMOVE_COLUMN)

    MODIFY_NULLABLE = 'modify_nullable'
    MODIFY_TYPE = 'modify_type'
    MODIFY_DEFAULT = 'modify_default'
    MODIFY_TYPES = (MODIFY_TYPE, MODIFY_DEFAULT, MODIFY_NULLABLE)

    ADD_CONSTRAINT = 'add_constraint'
    REMOVE_CONSTRAINT = 'remove_constraint'

    ADD_INDEX = 'add_index'
    REMOVE_INDEX = 'remove_index'
    INDEX_TYPES = (ADD_INDEX, REMOVE_INDEX)

    ADD_NULLABLE_COLUMN = 'add_nullable_column'
    MIGRATEABLE_TYPES = (ADD_NULLABLE_COLUMN,) + INDEX_TYPES

    CONSTRAINT_TYPES = (ADD_CONSTRAINT, REMOVE_CONSTRAINT) + INDEX_TYPES

    ALL = TABLE_TYPES + COLUMN_TYPES + MODIFY_TYPES + CONSTRAINT_TYPES

    TYPES_FOR_REBUILD = TABLE_TYPES + COLUMN_TYPES + (MODIFY_TYPE, MODIFY_NULLABLE)


class RebuildTableException(Exception):
    pass


def catch_signal(sender, **kwargs):
    from fluff.pillow import get_fluff_pillow_configs
    if settings.UNIT_TESTING or kwargs['using'] != DEFAULT_DB_ALIAS:
        return

    table_pillow_map = {}
    for config in get_fluff_pillow_configs():
        pillow = config.get_instance()
        for processor in pillow.processors:
            doc = processor.indicator_class()
            if doc.save_direct_to_sql:
                table_pillow_map[doc._table.name] = {
                    'doc': doc,
                    'pillow': pillow
                }

    print('\tchecking fluff SQL tables for schema changes')
    engine = connection_manager.get_engine('default')

    with engine.begin() as connection:
        migration_context = get_migration_context(connection, list(table_pillow_map))
        raw_diffs = compare_metadata(migration_context, fluff_metadata)

    _, diffs = reformat_alembic_diffs(raw_diffs)
    tables_to_rebuild = get_tables_to_rebuild(diffs, list(table_pillow_map))

    for table in tables_to_rebuild:
        info = table_pillow_map[table]
        rebuild_table(engine, info['pillow'], info['doc'])

    engine.dispose()


@attr.s(frozen=True)
class SimpleDiff(object):
    type = attr.ib()
    table_name = attr.ib()
    item_name = attr.ib()

    def to_dict(self):
        return {
            'type': self.type,
            'item_name': self.item_name
        }


def reformat_alembic_diffs(raw_diffs):
    """
    See: http://alembic.readthedocs.io/en/latest/api/autogenerate.html
    :param raw_diffs: from alembic
    :return: list of ``SimpleDiff`` tuples
    """
    diffs = []

    def _simplify_diff(raw_diff):
        type_ = raw_diff[0]
        if type_ in DiffTypes.TABLE_TYPES:
            diffs.append(
                SimpleDiff(type_, raw_diff[1].name, None)
            )
        elif type_ in DiffTypes.CONSTRAINT_TYPES:
            any_column = list(raw_diff[1].columns.values())[0]
            table_name = any_column.table.name
            diffs.append(
                SimpleDiff(type_, table_name, raw_diff[1].name)
            )
        elif type_ in DiffTypes.MODIFY_TYPES:
            diffs.append(
                SimpleDiff(type_, raw_diff[2], raw_diff[3])
            )
        elif type_ == DiffTypes.ADD_COLUMN and raw_diff[3].nullable:
            diffs.append(
                SimpleDiff(DiffTypes.ADD_NULLABLE_COLUMN, raw_diff[2], raw_diff[3].name)
            )
        elif type_ in DiffTypes.COLUMN_TYPES:
            diffs.append(
                SimpleDiff(type_, raw_diff[2], raw_diff[3].name)
            )
        else:
            diffs.append(SimpleDiff(type_, None, None))

    flattened_raw = []
    for diff in raw_diffs:
        if isinstance(diff, list):
            for d in diff:
                flattened_raw.append(d)
                _simplify_diff(d)
        else:
            flattened_raw.append(diff)
            _simplify_diff(diff)

    return flattened_raw, diffs


def get_tables_to_rebuild(diffs, table_names):
    return {
        diff.table_name
        for diff in diffs
        if diff.table_name in table_names and diff.type in DiffTypes.TYPES_FOR_REBUILD
    }



def rebuild_table(engine, pillow, indicator_doc):
    if pillow:
        logger.warn('Rebuilding table and resetting checkpoint for %s', pillow.get_name())
    table = indicator_doc._table
    with engine.begin() as connection:
        table.drop(connection, checkfirst=True)
        table.create(connection)
        owner = getattr(settings, 'SQL_REPORTING_OBJECT_OWNER', None)
        if owner:
            connection.execute('ALTER TABLE "%s" OWNER TO %s' % (table.name, owner))
    if pillow:
        pillow.reset_checkpoint()


def get_migration_context(connection, table_names=None, include_object=None):
    opts = {'compare_type': True}

    if callable(include_object):
        opts['include_object'] = include_object
    else:
        opts['include_symbol'] = partial(include_symbol, table_names)

    return MigrationContext.configure(connection, opts=opts)


def include_symbol(names_to_include, table_name, schema):
    return table_name in names_to_include
