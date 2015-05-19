# encoding: utf-8
import logging
import mock
from south.db import db
from south.v2 import DataMigration
from django.db import models
from django.db.utils import DatabaseError
from sqlalchemy import Unicode, UnicodeText, DDL
from corehq.db import Session

from dimagi.utils.couch import sync_docs
from corehq.apps.userreports import models as userreports_models
from corehq.apps.userreports import sql
from fluff.util import get_column_type

logger = logging.getLogger(__name__)


def old_get_column_type(data_type):
    """
    We patch corehq.apps.userreports.sql with this function to replicate the
    old behavior.
    """
    return get_column_type(data_type)


class Migration(DataMigration):


    def forwards(self, orm):

        _sync_couch()
        tables = _get_all_pre_migration_tables()

        session = Session()
        try:
            connection = session.connection()
            for table in tables:
                logger.info("Checking table {}".format(table.name))
                for column in table.columns:
                    if _should_alter_column(column):
                        logger.info("Altering {}".format(column))
                        _alter_column(connection, table, column)
                    else:
                        logger.info("Skipping {}".format(column))
        except:
            session.rollback()
            raise
        finally:
            # TODO: delete next line
            session.rollback()
            session.close()

        # TODO: Confirm that the tables are exactly the same as expected

    def backwards(self, orm):
        # Get the tables
        # Get the Text columns
        # Convert them to varchar(255)
        # Note, this would not be failsafe if somone introduces some other text type of field later.

    models = {}
    complete_apps = ['userreports']


def _sync_couch():
    """
    Sync couch docs before running the sql migration as it requires data from couch
    """
    sync_docs.sync(userreports_models, verbosity=2)

@mock.patch('corehq.apps.userreports.sql._get_column_type', old_get_column_type)
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
    #import ipdb; ipdb.set_trace()
    if isinstance(col.type, Unicode):
        if col.type.length == 255:
            return True
        else:
            raise Exception("Unexpted Unicode column length: {}".format(col.type.length))
    return False


def _alter_column(connection, table, column):
    # NOTE: For some reason table.compile(dialect=connection.dialect) returns an empty string...
    table_name = table.name
    #column_name = column.compile(dialect=connection.dialect)
    column_name = column.name
    column_type = UnicodeText().compile(connection.dialect)
    # TODO: Ensure this is not vulnerable to injection.
    statement = 'ALTER TABLE "{n}" ALTER COLUMN "{c}" TYPE {t}'.format(
        n=table_name,
        c=column_name,
        t=column_type
    )
    print statement
    connection.execute(statement)
