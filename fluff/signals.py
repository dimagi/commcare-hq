from functools import partial
import pprint
import sqlalchemy
import logging
from django.dispatch import Signal
from django.conf import settings
from itertools import chain
from django.db.models import signals
from pillowtop.utils import get_pillow_class, get_all_pillow_configs
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from fluff.util import metadata as fluff_metadata

logger = logging.getLogger('fluff')

BACKEND_COUCH = 'COUCH'
BACKEND_SQL = 'SQL'

indicator_document_updated = Signal(providing_args=["doc", "diff", "backend"])


class RebuildTableException(Exception):
    pass


def catch_signal(sender, **kwargs):
    if settings.UNIT_TESTING:
        return

    from fluff.pillow import FluffPillow
    table_pillow_map = {}
    pillow_configs = get_all_pillow_configs()
    for pillow_config in pillow_configs:
        pillow_class = pillow_config.get_class()
        if issubclass(pillow_class, FluffPillow):
            doc = pillow_class.indicator_class()
            if doc.save_direct_to_sql:
                table_pillow_map[doc._table.name] = {
                    'doc': doc,
                    'pillow': pillow_class
                }

    print '\tchecking fluff SQL tables for schema changes'
    engine = sqlalchemy.create_engine(settings.SQL_REPORTING_DATABASE_URL)

    with engine.begin() as connection:
        migration_context = get_migration_context(connection, table_pillow_map.keys())
        diffs = compare_metadata(migration_context, fluff_metadata)

    tables_to_rebuild = get_tables_to_rebuild(diffs, table_pillow_map.keys())

    for table in tables_to_rebuild:
        info = table_pillow_map[table]
        rebuild_table(engine, info['pillow'], info['doc'])

    engine.dispose()


def get_tables_to_rebuild(diffs, table_names):

    def check_diff(diff):
        """
        See: http://alembic.readthedocs.org/en/latest/api.html#autogeneration
        """
        if diff[0] in ('add_table', 'remove_table'):
            if diff[1].name in table_names:
                return diff[1].name
        elif diff[2] in table_names:
            return diff[2]

    def yield_diffs(diff_list):
        for diff in diff_list:
            if isinstance(diff, list):
                for d in diff:
                    yield check_diff(d)
            else:
                yield check_diff(diff)

    return [table for table in yield_diffs(diffs) if table]


def rebuild_table(engine, pillow_class, indicator_doc):
    logger.warn('Rebuilding table and resetting checkpoint for %s', pillow_class)
    table = indicator_doc._table
    with engine.begin() as connection:
        table.drop(connection, checkfirst=True)
        table.create(connection)
        owner = getattr(settings, 'SQL_REPORTING_OBJECT_OWNER', None)
        if owner:
            connection.execute('ALTER TABLE "%s" OWNER TO %s' % (table.name, owner))
    if pillow_class:
        pillow_class().reset_checkpoint()


def get_migration_context(connection, table_names):
    opts = {
        'include_symbol': partial(include_symbol, table_names),
    }
    return MigrationContext.configure(connection, opts=opts)


def include_symbol(names_to_include, table_name, schema):
    return table_name in names_to_include
