from contextlib import contextmanager
from unittest.mock import patch

import pytest
import sqlalchemy
from unmagic import use

from corehq.apps.project_db.table_ddl import (
    CaseTable,
    DomainSchema,
    create_or_update_project_db,
    get_project_db_engine,
)

from .util import project_db_table


def test_schema_name():
    assert DomainSchema('my-domain').name == 'projectdb_my-domain'


@pytest.mark.parametrize('domain, expected', [
    ('mydomain', 'projectdb_mydomain'),
    ('my-domain', '"projectdb_my-domain"'),
    ('my"domain', '"projectdb_my""domain"'),
])
def test_quoted_name(domain, expected):
    assert DomainSchema(domain)._quoted_name == expected


@use('db')
def test_schema_lifecycle():
    engine = get_project_db_engine()
    schema = DomainSchema('testprojectdb')
    with engine.begin() as conn:
        schema.create(conn)
        assert schema.name in sqlalchemy.inspect(conn).get_schema_names()

        schema.set_local_search_path(conn)
        search_path = conn.execute(sqlalchemy.text('SHOW search_path')).scalar()
        assert search_path == schema.name

        schema.drop(conn)
        assert schema.name not in sqlalchemy.inspect(conn).get_schema_names()


def test_case_table_basics():
    with patch.object(CaseTable, '_get_dd_properties', return_value=[
        ('nickname', 'plain'),
        ('favorite_color', 'select'),
        ('dob', 'date'),
        ('children_count', 'number'),
    ]):
        table = (CaseTable('test-domain', 'person')
                 .build_definition(sqlalchemy.MetaData()))

    assert table.name == 'person'
    assert table.schema == 'projectdb_test-domain'

    for column in CaseTable._static_columns():
        assert column.name in table.c

    assert isinstance(table.c['prop__nickname'].type, sqlalchemy.Text)
    assert isinstance(table.c['prop__favorite_color'].type, sqlalchemy.Text)
    assert isinstance(table.c['prop__dob'].type, sqlalchemy.Text)
    assert isinstance(table.c['date_prop__dob'].type, sqlalchemy.Date)
    assert isinstance(table.c['prop__children_count'].type, sqlalchemy.Text)
    assert isinstance(table.c['number_prop__children_count'].type, sqlalchemy.Numeric)

    # Text property columns are NOT NULL; typed columns stay nullable
    assert table.c['prop__nickname'].nullable is False
    assert table.c['prop__dob'].nullable is False
    assert table.c['date_prop__dob'].nullable is True
    assert table.c['number_prop__children_count'].nullable is True


@contextmanager
def _project_db_schema(domain):
    schema = DomainSchema(domain)
    try:
        yield schema
    finally:
        with get_project_db_engine().begin() as conn:
            schema.drop(conn)


@use('db', _project_db_schema('test_create_project_db'))
@patch('corehq.apps.project_db.table_ddl._get_case_types')
@patch.object(CaseTable, '_get_dd_properties')
def test_create_project_db(get_dd_properties, get_case_types):
    # Actually commit the project_db definition to postgres and spot check results
    domain = 'test_create_project_db'
    schema_name = DomainSchema(domain).name

    get_case_types.return_value = ['patient']
    get_dd_properties.return_value = [('nickname', 'plain'), ('dob', 'plain')]
    create_or_update_project_db(domain)
    _assert_db_created_as_expected(schema_name)

    # Drop nickname, make dob a date, add a new prop
    get_dd_properties.return_value = [('favorite_color', 'plain'), ('dob', 'date')]
    create_or_update_project_db(domain)
    _assert_db_updated_as_expected(schema_name)


def _assert_db_created_as_expected(schema):
    with get_project_db_engine().begin() as conn:
        inspector = sqlalchemy.inspect(conn)
        assert schema in inspector.get_schema_names()
        assert ['patient'] == inspector.get_table_names(schema=schema)

        cols = {col['name']: col for col in inspector.get_columns('patient', schema=schema)}
        col_types = {name: col['type'] for name, col in cols.items()}
        assert isinstance(col_types['case_name'], sqlalchemy.Text)
        assert isinstance(col_types['opened_on'], sqlalchemy.DateTime)
        assert isinstance(col_types['prop__nickname'], sqlalchemy.Text)
        assert isinstance(col_types['prop__dob'], sqlalchemy.Text)
        assert 'date_prop__dob' not in cols

        # Text property columns and external_id are NOT NULL, defaulting to ''
        for name in ['prop__nickname', 'prop__dob', 'external_id']:
            assert cols[name]['nullable'] is False, name
            assert cols[name]['default'] == "''::text", name
        # Other columns remain nullable
        assert cols['case_name']['nullable'] is True
        assert cols['parent_id']['nullable'] is True

        indexes = inspector.get_indexes('patient', schema=schema)
        assert any(ix['column_names'] == ['owner_id'] for ix in indexes)
        assert any(ix['column_names'] == ['parent_id'] for ix in indexes)


def _assert_db_updated_as_expected(schema):
    with get_project_db_engine().begin() as conn:
        inspector = sqlalchemy.inspect(conn)
        # still only the one table
        assert ['patient'] == inspector.get_table_names(schema=schema)

        columns = {
            col['name']: col['type']
            for col in inspector.get_columns('patient', schema=schema)
        }
        # New column added
        assert isinstance(columns['prop__favorite_color'], sqlalchemy.Text)
        # Column for deleted case property is still present
        assert isinstance(columns['prop__nickname'], sqlalchemy.Text)
        # Both a plain and a date column for dob
        assert isinstance(columns['prop__dob'], sqlalchemy.Text)
        assert isinstance(columns['date_prop__dob'], sqlalchemy.Date)


@use('db', project_db_table('test-reflect', 'patient', {
    'nickname': 'plain',
    'dob': 'date'
}))
def test_case_table_reflect():
    table = CaseTable('test-reflect', 'patient').reflect()
    assert table.name == 'patient'
    assert table.schema == 'projectdb_test-reflect'
    for column in CaseTable._static_columns():
        assert column.name in table.c
    assert isinstance(table.c['prop__nickname'].type, sqlalchemy.Text)
    assert isinstance(table.c['prop__dob'].type, sqlalchemy.Text)
    assert isinstance(table.c['date_prop__dob'].type, sqlalchemy.Date)
