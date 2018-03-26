from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings
from sqlalchemy.exc import ProgrammingError
from corehq.sql_db.config import partition_config

from corehq.sql_db.connections import connection_manager
from corehq.util.decorators import ContextDecorator


class temporary_database(ContextDecorator):
    """Create a database temporarily and remove it afterwards.
    """
    def __init__(self, database_name):
        self.database_name = database_name
        # use db1 engine to create db2 http://stackoverflow.com/a/8977109/8207
        self.root_engine = connection_manager.get_engine('default')

    def __enter__(self):
        conn = self.root_engine.connect()
        conn.execute('commit')
        try:
            conn.execute('CREATE DATABASE {}'.format(self.database_name))
        except ProgrammingError:
            # optimistically assume it failed because was already created.
            pass
        conn.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        conn = self.root_engine.connect()
        conn.execute('rollback')
        try:
            conn.execute('DROP DATABASE {}'.format(self.database_name))
        finally:
            conn.close()
            self.root_engine.dispose()


class DefaultShardingTestConfigMixIn(object):
    """
    Mixin with test cases to ensure sharding is setup according to the expected defaults
    """
    db1 = 'p1'
    db2 = 'p2'

    def test_settings(self):
        """
        The tests in this class assume a certain partitioned setup to ensure the
        partitioning is working properly, so this test makes sure those assumptions
        are valid.
        """

        self.assertEqual(len(settings.PARTITION_DATABASE_CONFIG['shards']), 2)
        self.assertIn(self.db1, settings.PARTITION_DATABASE_CONFIG['shards'])
        self.assertIn(self.db2, settings.PARTITION_DATABASE_CONFIG['shards'])
        self.assertEqual(settings.PARTITION_DATABASE_CONFIG['shards'][self.db1], [0, 1])
        self.assertEqual(settings.PARTITION_DATABASE_CONFIG['shards'][self.db2], [2, 3])
        self.assertEqual(set(partition_config.get_form_processing_dbs()), set([self.db1, self.db2]))
