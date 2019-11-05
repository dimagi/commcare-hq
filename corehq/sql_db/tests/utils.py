from sqlalchemy.exc import ProgrammingError

from corehq.sql_db.config import partition_config
from corehq.sql_db.connections import connection_manager, DEFAULT_ENGINE_ID
from corehq.util.decorators import ContextDecorator


class temporary_database(ContextDecorator):
    """Create a database temporarily and remove it afterwards.
    """
    def __init__(self, database_name):
        self.database_name = database_name
        # use db1 engine to create db2 http://stackoverflow.com/a/8977109/8207
        self.root_engine = connection_manager.get_engine(DEFAULT_ENGINE_ID)

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
        self.assertEqual(len(partition_config.shard_map), 2)
        self.assertIn(self.db1, partition_config.shard_map)
        self.assertIn(self.db2, partition_config.shard_map)
        self.assertEqual(partition_config.shard_map[self.db1], [0, 1])
        self.assertEqual(partition_config.shard_map[self.db2], [2, 3])
        self.assertEqual(set(partition_config.form_processing_dbs), set([self.db1, self.db2]))
