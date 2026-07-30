import pytest
from sqlalchemy import column, select, table

from corehq.apps.project_db.user_sql import UnsupportedSQL, translate

CLIENT = table('client', column('case_id'), column('name'))
TABLES = {'client': CLIENT}


@pytest.mark.parametrize('sql, expected', [
    ('SELECT * FROM client', select([CLIENT])),
    ('SELECT name, case_id FROM client', select([CLIENT.c.name, CLIENT.c.case_id])),
])
def test_valid_queries(sql, expected):
    result = translate(sql, TABLES)
    assert str(result) == str(expected)


@pytest.mark.parametrize('sql', [
    # Invalid SQL
    'SELECT * FROM (((',            # unbalanced parens
    'SELECT FROM',                  # missing projection
    "SELECT * FROM 'unclosed",      # unterminated string literal
    'SELECT * FROM client WHERE $$',  # untokenizable

    # Not (yet) supported
    'SELECT case_id AS id FROM client',   # column alias
    'SELECT * FROM client WHERE 1=1',     # extra clause
    'SELECT * FROM client LIMIT 5',       # extra clause
    'SELECT * FROM client, client',       # more than one table
    'SELECT * FROM (SELECT * FROM client) AS t',  # subquery is not a table
    'SELECT * FROM generate_series(1, 10)',  # table valued function not supported
    "INSERT INTO client VALUES ('x')",    # not a SELECT
    'SELECT * FROM client; SELECT * FROM client',  # multiple statements
    'SELECT * FROM unknown',              # unknown table
    'SELECT * FROM otherdomain.client',   # schema-qualified table
    'SELECT missing FROM client',         # unknown column
    'SELECT client.name FROM client',     # table-qualified column
    'SELECT bogus.name FROM client',      # qualified by some other table
])
def test_rejects_unsupported(sql):
    with pytest.raises(UnsupportedSQL):
        translate(sql, TABLES)


def test_handle_quoted_tables():
    hyphenated_table = table('hyphenated-table', column('case_id'))
    tables = {'hyphenated-table': hyphenated_table}
    result = translate('SELECT * FROM "hyphenated-table"', tables)
    assert str(result) == str(select([hyphenated_table]))
