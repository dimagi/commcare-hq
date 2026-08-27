import pytest
from sqlalchemy import column, table

from corehq.apps.project_db.cases import get_case_id_column
from corehq.apps.project_db.user_sql import UnsupportedSQL, translate

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
