import pprint
import sqlalchemy
import logging
from django.dispatch import Signal
from django.conf import settings
from itertools import chain
from django.db.models import signals
from pillowtop.utils import import_pillow_string
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata

logger = logging.getLogger('fluff')

indicator_document_updated = Signal(providing_args=["diff"])

class RebuildTableException(Exception):
    pass


def catch_signal(app, **kwargs):
    app_name = app.__name__.rsplit('.', 1)[0]
    if app_name == 'fluff':
        from fluff import FluffPillow

        pillows = list(chain.from_iterable(settings.PILLOWTOPS.values()))
        for pillow_string in pillows:
            pillow_class = import_pillow_string(pillow_string, instantiate=False)
            if issubclass(pillow_class, FluffPillow):
                doc_class = pillow_class.indicator_class
                create_update_indicator_table(doc_class, pillow_class)


def create_update_indicator_table(doc_class, pillow_class):
    doc = doc_class()
    if doc.save_direct_to_sql:
        try:
            check_table(doc)
        except RebuildTableException:
            rebuild_table(pillow_class, doc)


def check_table(indicator_doc):
    def check_diff(diff):
        if diff[0] in ('add_table', 'remove_table'):
            if diff[1].name == table_name:
                raise RebuildTableException()
        elif diff[2] == table_name:
            raise RebuildTableException()

    table_name = indicator_doc._table.name
    diffs = compare_metadata(get_migration_context(), indicator_doc._table.metadata)
    for diff in diffs:
        if isinstance(diff, list):
            for d in diff:
                check_diff(d)
        else:
            check_diff(diff)


def rebuild_table(pillow_class, indicator_doc):
    logger.warn('Rebuilding table and resetting checkpoint for %s', pillow_class)
    table = indicator_doc._table
    with get_engine().begin() as connection:
            table.drop(connection, checkfirst=True)
            table.create(connection)
            owner = getattr(settings, 'SQL_REPORTING_OBJECT_OWNER', None)
            if owner:
                connection.execute('ALTER TABLE "%s" OWNER TO %s' % (table.name, owner))
    if pillow_class:
        pillow_class().reset_checkpoint()


def get_migration_context():
    if not hasattr(get_migration_context, '_mc') or get_migration_context._mc is None:
        get_migration_context._mc = MigrationContext.configure(get_engine().connect())
    return get_migration_context._mc


def get_engine():
    if not hasattr(get_engine, '_engine') or get_engine._engine is None:
        get_engine._engine = sqlalchemy.create_engine(settings.SQL_REPORTING_DATABASE_URL)
    return get_engine._engine


signals.post_syncdb.connect(catch_signal)

