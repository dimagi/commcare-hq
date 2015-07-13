# encoding: utf-8
import alembic
import logging
import mock
from fluff.util import get_column_type
from south.v2 import DataMigration
from sqlalchemy import Unicode, UnicodeText

from dimagi.utils.couch import sync_docs
from corehq.apps.userreports import models as userreports_models
from corehq.apps.userreports import sql
from corehq.db import Session


logger = logging.getLogger(__name__)


def old_get_column_type(data_type):
    """
    This function recreates the pre-migration behavior of
    corehq.apps.userreports.sql._get_column_type
    """
    return get_column_type(data_type)


class Migration(DataMigration):


    def forwards(self, orm):
        return _alter_tables_helper(_get_all_pre_migration_tables, _should_alter_column, _alter_column)

    def backwards(self, orm):
        # NOTE! This assumes all Text fields should go back to being varchar(255) fields.
        #       You will be very sad if you have data longer than 255 characters
        #       in your text fields
        return _alter_tables_helper(_get_all_tables, _should_reverse_column, _reverse_column)


    models = {}
    complete_apps = ['userreports']


def _alter_tables_helper(get_tables_func, column_checker_func, column_alter_func):
    _sync_couch()
    tables = get_tables_func()
    session = Session()

    try:
        connection = session.connection()
        ctx = alembic.migration.MigrationContext.configure(connection)
        op = alembic.operations.Operations(ctx)

        for table in tables:
            logger.info("Checking table {}".format(table.name))
            for column in table.columns:
                if column_checker_func(column):
                    logger.info("Altering {}".format(column))
                    column_alter_func(op, table, column)
                else:
                    logger.info("Skipping {}".format(column))
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


def _sync_couch():
    """
    Sync couch docs before running the sql migration as it requires data from couch
    """
    sync_docs.sync(userreports_models, verbosity=2)


@mock.patch('corehq.apps.userreports.sql.columns._get_column_type', old_get_column_type)
def _get_all_pre_migration_tables():
    return _get_all_tables()


def _get_all_tables():
    session = Session()
    try:
        connection = session.connection()
        tables = [
            sql.get_indicator_table(config) for config in
            userreports_models.DataSourceConfiguration.all()
        ]
        return [t for t in tables if t.exists(bind=connection)]
    except:
        session.rollback()
        raise
    finally:
        session.close()


def _should_alter_column(col):
    if isinstance(col.type, Unicode):
        if col.type.length == 255:
            return True
        else:
            raise Exception("Unexpected Unicode column length: {}".format(col.type.length))
    return False


def _alter_column(op, table, column):
    op.alter_column(table.name, column.name, type_=UnicodeText())


def _should_reverse_column(col):
    if isinstance(col.type, UnicodeText):
        return True
    return False


def _reverse_column(op, table, column):
    op.alter_column(table.name, column.name, type_=Unicode(length=255))
