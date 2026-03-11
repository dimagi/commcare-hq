import pytest
import sqlalchemy
from sqlalchemy import inspect as sa_inspect

from corehq.apps.project_db.schema import build_table_for_case_type
from corehq.apps.project_db.table_manager import (
    create_tables,
    evolve_table,
    get_project_db_engine,
)


def _table_exists(engine, table_name):
    return table_name in sa_inspect(engine).get_table_names()


@pytest.mark.django_db
class TestCreateTables:

    def setup_method(self):
        self.engine = get_project_db_engine()
        self._tables = []

    def teardown_method(self):
        for table in self._tables:
            table.drop(self.engine, checkfirst=True)

    def _build_and_track(self, metadata, domain, case_type, **kwargs):
        table = build_table_for_case_type(metadata, domain, case_type, **kwargs)
        self._tables.append(table)
        return table

    def test_create_table(self):
        metadata = sqlalchemy.MetaData()
        table = self._build_and_track(
            metadata, 'test-domain', 'person',
            properties=[('name', 'plain')],
        )

        create_tables(self.engine, metadata)

        assert _table_exists(self.engine, table.name)

    def test_create_is_idempotent(self):
        metadata = sqlalchemy.MetaData()
        table = self._build_and_track(
            metadata, 'test-domain', 'person2',
            properties=[('name', 'plain')],
        )

        create_tables(self.engine, metadata)
        create_tables(self.engine, metadata)

        assert _table_exists(self.engine, table.name)


@pytest.mark.django_db
class TestEvolveTable:

    def setup_method(self):
        self.engine = get_project_db_engine()
        self._tables = []

    def teardown_method(self):
        for table in self._tables:
            table.drop(self.engine, checkfirst=True)

    def _build_and_track(self, metadata, domain, case_type, **kwargs):
        table = build_table_for_case_type(metadata, domain, case_type, **kwargs)
        self._tables.append(table)
        return table

    def test_add_new_column(self):
        metadata = sqlalchemy.MetaData()
        self._build_and_track(
            metadata, 'test-domain', 'evolve1',
            properties=[('name', 'plain')],
        )
        create_tables(self.engine, metadata)

        # Build a new definition with an additional property
        metadata2 = sqlalchemy.MetaData()
        table2 = build_table_for_case_type(
            metadata2, 'test-domain', 'evolve1',
            properties=[('name', 'plain'), ('age', 'number')],
        )

        evolve_table(self.engine, table2)

        columns = {c['name'] for c in sa_inspect(self.engine).get_columns(table2.name)}
        assert 'prop__age' in columns
        assert 'prop__age__numeric' in columns

    def test_add_new_index(self):
        metadata = sqlalchemy.MetaData()
        table = self._build_and_track(
            metadata, 'test-domain', 'evolve-idx',
            properties=[('name', 'plain')],
        )
        create_tables(self.engine, metadata)

        # Build a new definition and add an extra index
        metadata2 = sqlalchemy.MetaData()
        table2 = build_table_for_case_type(
            metadata2, 'test-domain', 'evolve-idx',
            properties=[('name', 'plain')],
        )
        sqlalchemy.Index(f'ix_{table2.name}_case_name', table2.c['case_name'])

        evolve_table(self.engine, table2)

        index_names = {
            idx['name'] for idx in sa_inspect(self.engine).get_indexes(table2.name)
        }
        assert f'ix_{table2.name}_case_name' in index_names

    def test_evolve_does_not_drop_columns(self):
        metadata = sqlalchemy.MetaData()
        self._build_and_track(
            metadata, 'test-domain', 'evolve2',
            properties=[('name', 'plain'), ('village', 'plain')],
        )
        create_tables(self.engine, metadata)

        # Build a new definition that lacks the 'village' property
        metadata2 = sqlalchemy.MetaData()
        table2 = build_table_for_case_type(
            metadata2, 'test-domain', 'evolve2',
            properties=[('name', 'plain')],
        )

        evolve_table(self.engine, table2)

        columns = {c['name'] for c in sa_inspect(self.engine).get_columns(table2.name)}
        assert 'prop__village' in columns
