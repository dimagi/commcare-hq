import pytest
from sqlalchemy import column, table
from unmagic import use

from corehq.apps.project_db.cases import get_case_id_column, rows_to_cases
from corehq.apps.project_db.table_ddl import (
    get_domain_tables,
    get_project_db_engine,
    property_column,
)
from corehq.apps.project_db.user_sql import UnsupportedSQL, translate

from .util import project_db_table

PARENT = table('parent', column('case_id'), column('name'))
CHILD = table('child', column('case_id'), column('parent_id'), column('name'))
TABLES = {'parent': PARENT, 'child': CHILD}
JOIN = 'FROM parent JOIN child ON parent.case_id = child.parent_id'


@pytest.mark.parametrize('sql, expected_table', [
    ('SELECT case_id FROM parent', 'parent'),
    ('SELECT * FROM parent', 'parent'),
    ('SELECT parent.case_id, name FROM parent', 'parent'),
    (f'SELECT child.case_id {JOIN}', 'child'),
    # Aliasing one away resolves what would otherwise be ambiguous
    (f'SELECT parent.case_id AS pid, child.case_id {JOIN}', 'child'),
    ("SELECT case_id FROM parent UNION SELECT case_id FROM parent "
     "WHERE name = 'x'", 'parent'),
])
def test_finds_the_case_id_column(sql, expected_table):
    col = get_case_id_column(translate(sql, TABLES))
    assert col.name == 'case_id'
    assert col.table.name == expected_table


@pytest.mark.parametrize('sql', [
    'SELECT name FROM parent',                       # not selected
    'SELECT case_id AS id FROM parent',              # aliased away
    f'SELECT * {JOIN}',                              # ambiguous: both tables
    f'SELECT parent.case_id, child.case_id {JOIN}',  # ambiguous: explicit
    'SELECT name FROM parent UNION SELECT name FROM child',
    # Each leg is a different case type, so the results would have no
    # single type and no single set of property columns
    'SELECT case_id FROM parent UNION SELECT case_id FROM child',
])
def test_rejects_missing_or_ambiguous(sql):
    with pytest.raises(UnsupportedSQL):
        get_case_id_column(translate(sql, TABLES))


LONG_NAME = 'a_very_long_property_name_that_will_certainly_be_truncated_by_pg'


@use('db', project_db_table('rows-to-cases', 'patient', {
    'nickname': 'plain', 'dob': 'date', LONG_NAME: 'plain',
}))
def test_rows_to_cases():
    table = get_domain_tables('rows-to-cases')['patient']
    with get_project_db_engine().begin() as conn:
        conn.execute(table.insert().values(
            case_id='c1', owner_id='o1', case_name='Ann', closed=False,
            external_id='', **{
                property_column('nickname'): 'Annie',
                property_column('dob'): '2020-01-01',
                property_column(LONG_NAME): 'long',
            }))
        rows = conn.execute(table.select()).fetchall()

    case, = rows_to_cases(rows, 'rows-to-cases', table)
    assert case.case_id == 'c1'
    assert case.domain == 'rows-to-cases'
    assert case.type == 'patient'
    assert case.name == 'Ann'
    assert case.owner_id == 'o1'
    assert case.closed is False
    assert case.indices == []
    # The column comment carries the raw name, so a truncated column resolves
    assert case.case_json == {
        'nickname': 'Annie', 'dob': '2020-01-01', LONG_NAME: 'long',
    }


@use('db', project_db_table('rows-partial', 'patient', {'nickname': 'plain'}))
def test_rows_to_cases_uses_only_the_selected_columns():
    table = get_domain_tables('rows-partial')['patient']
    with get_project_db_engine().begin() as conn:
        conn.execute(table.insert().values(
            case_id='c1', owner_id='o1', case_name='Ann', closed=False,
            external_id='', **{property_column('nickname'): 'Annie'}))
        rows = conn.execute(
            table.select().with_only_columns([table.c.case_id])).fetchall()

    case, = rows_to_cases(rows, 'rows-partial', table)
    assert case.case_id == 'c1'
    assert case.name is None
    assert case.case_json == {}
