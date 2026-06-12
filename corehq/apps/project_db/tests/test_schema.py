from unittest.mock import patch

import pytest
import sqlalchemy
from unmagic import use

from corehq.apps.project_db.schema import (
    CaseTable,
    DomainSchema,
    create_or_update_project_db,
    get_project_db_engine,
)


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
    assert isinstance(table.c['prop__dob__date'].type, sqlalchemy.Date)
    assert isinstance(table.c['prop__children_count'].type, sqlalchemy.Text)
    assert isinstance(table.c['prop__children_count__number'].type, sqlalchemy.Numeric)


@use('db')
@patch('corehq.apps.project_db.schema._get_case_types')
@patch.object(CaseTable, '_get_dd_properties')
def test_create_project_db(get_dd_properties, get_case_types):
    # Actually commit the project_db definition to postgres and spot check results
    domain = 'test_create_project_db'
    domain_schema = DomainSchema(domain)

    get_case_types.return_value = ['patient']
    get_dd_properties.return_value = [('nickname', 'plain'), ('dob', 'date')]
    create_or_update_project_db(domain)
    _assert_db_created_as_expected(domain_schema.name)

    get_dd_properties.return_value = [('favorite_color', 'plain'), ('dob', 'date')]
    create_or_update_project_db(domain)
    _assert_db_updated_as_expected(domain_schema.name)

    with get_project_db_engine().begin() as conn:
        domain_schema.drop(conn)


def _assert_db_created_as_expected(schema):
    with get_project_db_engine().begin() as conn:
        inspector = sqlalchemy.inspect(conn)
        assert schema in inspector.get_schema_names()
        assert ['patient'] == inspector.get_table_names(schema=schema)

        columns = {
            col['name']: col['type']
            for col in inspector.get_columns('patient', schema=schema)
        }
        assert isinstance(columns['case_name'], sqlalchemy.Text)
        assert isinstance(columns['opened_on'], sqlalchemy.DateTime)
        assert isinstance(columns['prop__nickname'], sqlalchemy.Text)
        assert isinstance(columns['prop__dob__date'], sqlalchemy.Date)

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
