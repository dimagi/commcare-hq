from __future__ import absolute_import
from __future__ import unicode_literals
import uuid

import sqlalchemy
from alembic.autogenerate import compare_metadata
from django.test.testcases import TestCase, SimpleTestCase
from nose.tools import assert_list_equal

from corehq.sql_db.connections import connection_manager
from fluff.signals import (
    get_migration_context, reformat_alembic_diffs,
    SimpleDiff, DiffTypes, get_tables_to_rebuild
)


def test_flatten_raw_diffs():
    raw_diffs = [
        [('diff1', None)],
        [('diff2', None)],
        ('diff3', None),
    ]
    flattened = reformat_alembic_diffs(raw_diffs)
    assert_list_equal(flattened, [
        SimpleDiff('diff1', None, None, ('diff1', None)),
        SimpleDiff('diff2', None, None, ('diff1', None)),
        SimpleDiff('diff3', None, None, ('diff1', None)),
    ])


class TestAlembicDiffs(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestAlembicDiffs, cls).setUpClass()
        cls.engine = connection_manager.get_engine()
        cls.metadata = sqlalchemy.MetaData()
        cls.table_name = 'diff_table_' + uuid.uuid4().hex
        sqlalchemy.Table(
            cls.table_name, cls.metadata,
            sqlalchemy.Column('user_id', sqlalchemy.Integer, primary_key=True),
            sqlalchemy.Column('user_name', sqlalchemy.String(16), nullable=False),
            sqlalchemy.Column('email_address', sqlalchemy.String(60), key='email'),
            sqlalchemy.Column('password', sqlalchemy.String(20), nullable=False),
        )
        cls.metadata.create_all(cls.engine)

    @classmethod
    def tearDownClass(cls):
        cls.metadata.drop_all(cls.engine)
        connection_manager.dispose_engine()
        super(TestAlembicDiffs, cls).tearDownClass()

    def setUp(self):
        self.transaction_context = self.engine.begin()
        self.connection = self.transaction_context.__enter__()

    def tearDown(self):
        self.transaction_context.__exit__(None, None, None)

    def test_table_filter(self):
        migration_context = get_migration_context(self.engine, [self.table_name])
        sqlalchemy.Table('new_table', self.metadata)
        raw_diffs = compare_metadata(migration_context, self.metadata)
        diffs = reformat_alembic_diffs(raw_diffs)
        self.assertEqual(0, len(diffs))

    def test_add_remove_table(self):
        metadata = sqlalchemy.MetaData()
        sqlalchemy.Table('new_table', metadata)
        self._test_diffs(metadata, {
            SimpleDiff(DiffTypes.ADD_TABLE, 'new_table', None, None),
            SimpleDiff(DiffTypes.REMOVE_TABLE, self.table_name, None, None),
        })

    def test_add_remove_column(self):
        metadata = sqlalchemy.MetaData()
        sqlalchemy.Table(
            self.table_name, metadata,
            sqlalchemy.Column('user_id', sqlalchemy.Integer, primary_key=True),
            sqlalchemy.Column('user_name', sqlalchemy.String(16), nullable=False),
            sqlalchemy.Column('email_address', sqlalchemy.String(60), key='email'),
            sqlalchemy.Column('new_password', sqlalchemy.String(20), nullable=False)
        )
        diffs = self._test_diffs(metadata, {
            SimpleDiff(DiffTypes.ADD_COLUMN, self.table_name, 'new_password', None),
            SimpleDiff(DiffTypes.REMOVE_COLUMN, self.table_name, 'password', None)
        })
        # check that we can get the column via the property
        self.assertIsNotNone(diffs[0].column)
        self.assertIsNotNone(diffs[1].column)

    def test_modify_column(self):
        metadata = sqlalchemy.MetaData()
        sqlalchemy.Table(
            self.table_name, metadata,
            sqlalchemy.Column('user_id', sqlalchemy.Integer, primary_key=True),
            sqlalchemy.Column('user_name', sqlalchemy.String(16), nullable=True),
            sqlalchemy.Column('email_address', sqlalchemy.String(60), key='email'),
            sqlalchemy.Column('password', sqlalchemy.Integer, nullable=False)
        )
        self._test_diffs(metadata, {
            SimpleDiff(DiffTypes.MODIFY_TYPE, self.table_name, 'password', None),
            SimpleDiff(DiffTypes.MODIFY_NULLABLE, self.table_name, 'user_name', None),
        })

    def _test_diffs(self, metadata, expected_diffs, table_names=None):
        migration_context = get_migration_context(self.engine, table_names or [self.table_name, 'new_table'])
        raw_diffs = compare_metadata(migration_context, metadata)
        diffs = reformat_alembic_diffs(raw_diffs)
        self.assertEqual(set(diffs), expected_diffs)
        return diffs


class TestTablesToRebuild(SimpleTestCase):
    def test_filter_by_type(self):
        diffs = {
            SimpleDiff(type_, type_, None, None)
            for type_ in DiffTypes.ALL
        }
        tables = get_tables_to_rebuild(diffs)
        self.assertEqual(
            tables,
            set(DiffTypes.TYPES_FOR_REBUILD)
        )
