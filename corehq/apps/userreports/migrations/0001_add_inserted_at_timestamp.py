# encoding: utf-8
import logging
from south.db import db
from south.v2 import DataMigration
from django.db import models
from django.db.utils import DatabaseError

from dimagi.utils.couch import sync_docs
from corehq.apps.userreports import models as userreports_models
from corehq.apps.userreports.sql import get_table_name

logger = logging.getLogger(__name__)


class Migration(DataMigration):

    def forwards(self, orm):
        """
        Adds an 'inserted_at' column to each existing data source table
        """
        _sync_couch()
        table_names = _get_all_table_names()

        num_tables = len(table_names)
        logger.info("Start adding inserted_at column to %s existing UCR datasource tables", num_tables)

        for table_name in table_names:
            try:
                logger.info("Adding inserted_at column to %s", table_name)
                db.start_transaction()
                db.add_column(table_name, 'inserted_at', models.DateTimeField(null=True))
            except DatabaseError:
                logger.warning("Adding inserted_at column failed for %s", table_name)
            finally:
                db.commit_transaction()

        logger.info("Finished adding inserted_at columns to existing UCR datasource tables")

    def backwards(self, orm):
        """
        Removes 'inserted_at' column from each data source table
        """
        _sync_couch()
        table_names = _get_all_table_names()

        for table_name in table_names:
            db.delete_column(table_name, 'inserted_at')

    models = {}

    complete_apps = ['userreports']


def _sync_couch():
    """
    Sync couch docs before running the sql migration as it requires data from couch
    """
    sync_docs.sync(userreports_models, verbosity=2)


def _get_all_table_names():
    return map(lambda dsc: get_table_name(dsc.domain, dsc.table_id),
               userreports_models.DataSourceConfiguration.all())
