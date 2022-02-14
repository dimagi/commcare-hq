import uuid
from unittest import SkipTest

from django.conf import settings

from sqlalchemy.exc import ProgrammingError

from corehq.sql_db.config import plproxy_config
from corehq.sql_db.connections import connection_manager, DEFAULT_ENGINE_ID
from corehq.sql_db.util import get_db_alias_for_partitioned_doc
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


def new_id_in_different_dbalias(partition_value):
    """
    Returns a new partition value from a different db alias than
    the given partition value does
    """
    if not settings.USE_PARTITIONED_DATABASE:
        raise SkipTest("cannot get different db alias for non-sharded db")
    old_db_name = get_db_alias_for_partitioned_doc(partition_value)
    new_db_name = old_db_name
    while old_db_name == new_db_name:
        # todo; guard against infinite loop
        new_partition_value = str(uuid.uuid4())
        new_db_name = get_db_alias_for_partitioned_doc(new_partition_value)
    return new_partition_value


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
        self.assertEqual(len(plproxy_config.shard_map), 2)
        self.assertIn(self.db1, plproxy_config.shard_map)
        self.assertIn(self.db2, plproxy_config.shard_map)
        self.assertEqual(plproxy_config.shard_map[self.db1], [0, 1])
        self.assertEqual(plproxy_config.shard_map[self.db2], [2, 3])
        self.assertEqual(set(plproxy_config.form_processing_dbs), set([self.db1, self.db2]))
