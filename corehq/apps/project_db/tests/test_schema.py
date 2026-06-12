import pytest
import sqlalchemy
from unmagic import use

from corehq.apps.project_db.schema import DomainSchema, get_project_db_engine, CaseTable


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


def test_case_table():
    table = CaseTable('test-domain', 'person').build_definition(sqlalchemy.MetaData())

    assert table.name == 'person'
    assert table.schema == 'projectdb_test-domain'

    for name, col_type, col_kwargs in CaseTable.STATIC_COLUMNS:
        column = table.c[name]
        assert isinstance(column.type, col_type)

    expected_indices = {f'ix_person_{column}' for column in [
        'owner_id', 'modified_on', 'parent_id', 'host_id'
    ]}
    assert expected_indices == {idx.name for idx in table.indexes}
