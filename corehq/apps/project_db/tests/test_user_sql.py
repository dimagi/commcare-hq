from decimal import Decimal

import pytest
from sqlalchemy import (
    and_,
    column,
    literal,
    not_,
    nullsfirst,
    nullslast,
    or_,
    select,
    table,
    union,
    union_all,
)
from sqlalchemy.dialects import postgresql

from corehq.apps.project_db.user_sql import UnsupportedSQL, translate

CLIENT = table('client', column('case_id'), column('name'))
VISIT = table('visit', column('visit_id'), column('parent_id'), column('name'))
FORM = table('form', column('form_id'), column('visit_id'))
TABLES = {'client': CLIENT, 'visit': VISIT, 'form': FORM}

ON = CLIENT.c.case_id == VISIT.c.parent_id
CLIENT_VISIT = CLIENT.join(VISIT, ON)
JOIN_SQL = 'FROM client JOIN visit ON client.case_id = visit.parent_id'


@pytest.mark.parametrize('sql, expected', [
    ('SELECT * FROM client', select([CLIENT])),
    ('SELECT name, case_id FROM client', select([CLIENT.c.name, CLIENT.c.case_id])),

    # Column aliases
    ('SELECT case_id AS id FROM client', select([CLIENT.c.case_id.label('id')])),
    ('SELECT case_id id FROM client', select([CLIENT.c.case_id.label('id')])),
    ('SELECT case_id AS "My Id" FROM client',
     select([CLIENT.c.case_id.label('My Id')])),

    ("SELECT * FROM client WHERE name = 'x'",
     select([CLIENT]).where(CLIENT.c.name == literal('x'))),
    ("SELECT * FROM client WHERE name <> 'x'",
     select([CLIENT]).where(CLIENT.c.name != literal('x'))),
    ('SELECT * FROM client WHERE case_id > 5',
     select([CLIENT]).where(CLIENT.c.case_id > literal(5))),
    ('SELECT * FROM client WHERE case_id <= 5.5',
     select([CLIENT]).where(CLIENT.c.case_id <= literal(Decimal('5.5')))),
    # Operands may appear in either order
    ("SELECT * FROM client WHERE 'x' = name",
     select([CLIENT]).where(literal('x') == CLIENT.c.name)),

    # Columns may be qualified by their table
    ('SELECT client.name FROM client', select([CLIENT.c.name])),
    ("SELECT * FROM client WHERE client.name = 'x'",
     select([CLIENT]).where(CLIENT.c.name == literal('x'))),

    # Joins
    (f'SELECT * {JOIN_SQL}', select([CLIENT_VISIT])),
    (f'SELECT client.name, visit.visit_id {JOIN_SQL}',
     select([CLIENT.c.name, VISIT.c.visit_id]).select_from(CLIENT_VISIT)),
    # An unqualified column is fine when only one table has it
    (f'SELECT parent_id {JOIN_SQL}',
     select([VISIT.c.parent_id]).select_from(CLIENT_VISIT)),
    (f"SELECT * {JOIN_SQL} WHERE visit.name = 'x'",
     select([CLIENT_VISIT]).where(VISIT.c.name == literal('x'))),
    (f'SELECT client.name, form.form_id {JOIN_SQL} '
     'JOIN form ON visit.visit_id = form.visit_id',
     select([CLIENT.c.name, FORM.c.form_id]).select_from(
         CLIENT_VISIT.join(FORM, VISIT.c.visit_id == FORM.c.visit_id))),
    ("SELECT * FROM client JOIN visit "
     "ON client.case_id = visit.parent_id AND visit.name = 'x'",
     select([CLIENT.join(VISIT, and_(ON, VISIT.c.name == literal('x')))])),
    ('SELECT * FROM client LEFT JOIN visit ON client.case_id = visit.parent_id',
     select([CLIENT.join(VISIT, ON, isouter=True)])),

    # DISTINCT
    ('SELECT DISTINCT name FROM client', select([CLIENT.c.name]).distinct()),
    # DISTINCT ON columns need not appear in the projection
    ('SELECT DISTINCT ON (case_id) name FROM client',
     select([CLIENT.c.name]).distinct(CLIENT.c.case_id)),
    ('SELECT DISTINCT ON (case_id, name) name FROM client',
     select([CLIENT.c.name]).distinct(CLIENT.c.case_id, CLIENT.c.name)),

    # ORDER BY - each key gets its own direction and default NULLS placement
    ('SELECT * FROM client ORDER BY name, case_id DESC',
     select([CLIENT]).order_by(nullslast(CLIENT.c.name.asc()),
                               nullsfirst(CLIENT.c.case_id.desc()))),
    # An explicit NULLS placement overrides the direction's default
    ('SELECT name FROM client ORDER BY name DESC NULLS LAST',
     select([CLIENT.c.name]).order_by(nullslast(CLIENT.c.name.desc()))),

    # Unions
    ('SELECT case_id FROM client UNION SELECT visit_id FROM visit',
     union(select([CLIENT.c.case_id]), select([VISIT.c.visit_id]))),
    ('SELECT case_id FROM client UNION ALL SELECT visit_id FROM visit',
     union_all(select([CLIENT.c.case_id]), select([VISIT.c.visit_id]))),
    # `client` and `form` both have two columns
    ('SELECT * FROM client UNION SELECT * FROM form',
     union(select([CLIENT]), select([FORM]))),
    ('SELECT case_id FROM client UNION SELECT visit_id FROM visit '
     'UNION SELECT form_id FROM form',
     union(union(select([CLIENT.c.case_id]), select([VISIT.c.visit_id])),
           select([FORM.c.form_id]))),
    ("SELECT case_id FROM client WHERE name = 'x' UNION SELECT visit_id FROM visit",
     union(select([CLIENT.c.case_id]).where(CLIENT.c.name == literal('x')),
           select([VISIT.c.visit_id]))),

    # WHERE clauses
    ("SELECT * FROM client WHERE name = 'x' AND case_id = 'c1'",
     select([CLIENT]).where(and_(CLIENT.c.name == literal('x'),
                                 CLIENT.c.case_id == literal('c1')))),
    ("SELECT * FROM client WHERE name = 'x' OR case_id = 'c1'",
     select([CLIENT]).where(or_(CLIENT.c.name == literal('x'),
                                CLIENT.c.case_id == literal('c1')))),
    ("SELECT * FROM client WHERE NOT name = 'x'",
     select([CLIENT]).where(not_(CLIENT.c.name == literal('x')))),
    ("SELECT * FROM client WHERE (name = 'x')",
     select([CLIENT]).where(CLIENT.c.name == literal('x'))),
    # Parentheses override the usual AND-before-OR precedence
    ("SELECT * FROM client WHERE (name = 'x' OR name = 'y') AND case_id = 'c1'",
     select([CLIENT]).where(and_(or_(CLIENT.c.name == literal('x'),
                                     CLIENT.c.name == literal('y')),
                                 CLIENT.c.case_id == literal('c1')))),
    ("SELECT * FROM client WHERE name = 'x' AND case_id = 'c1' AND name = 'y'",
     select([CLIENT]).where(and_(and_(CLIENT.c.name == literal('x'),
                                      CLIENT.c.case_id == literal('c1')),
                                 CLIENT.c.name == literal('y')))),
    ("SELECT * FROM client WHERE name IN ('x', 'y')",
     select([CLIENT]).where(CLIENT.c.name.in_([literal('x'), literal('y')]))),
    # The values may be any supported value expression, not just literals
    ('SELECT * FROM client WHERE name IN (case_id)',
     select([CLIENT]).where(CLIENT.c.name.in_([CLIENT.c.case_id]))),
    ("SELECT * FROM client WHERE name NOT IN ('x')",
     select([CLIENT]).where(not_(CLIENT.c.name.in_([literal('x')])))),
    ('SELECT * FROM client WHERE name = TRUE',
     select([CLIENT]).where(CLIENT.c.name == literal(True))),
    ('SELECT * FROM client WHERE name IS NULL',
     select([CLIENT]).where(CLIENT.c.name.is_(None))),
    ('SELECT * FROM client WHERE name IS NOT NULL',
     select([CLIENT]).where(CLIENT.c.name.isnot(None))),
    ('SELECT * FROM client WHERE NOT name IS NULL',
     select([CLIENT]).where(not_(CLIENT.c.name.is_(None)))),
    ('SELECT * FROM client WHERE name IS TRUE',
     select([CLIENT]).where(CLIENT.c.name.is_(True))),
    ('SELECT * FROM client WHERE name IS FALSE',
     select([CLIENT]).where(CLIENT.c.name.is_(False))),
    ('SELECT * FROM client WHERE name IS NOT TRUE',
     select([CLIENT]).where(not_(CLIENT.c.name.is_(True)))),
])
def test_valid_queries(sql, expected):
    assert _compiled(translate(sql, TABLES)) == _compiled(expected)


def _compiled(query):
    """Return a query's SQL and its bound parameters, with their types."""
    compiled = query.compile(dialect=postgresql.dialect())
    return str(compiled), {k: (type(v), v) for k, v in compiled.params.items()}


@pytest.mark.parametrize('sql', [
    # Invalid SQL
    'SELECT * FROM (((',            # unbalanced parens
    'SELECT FROM',                  # missing projection
    "SELECT * FROM 'unclosed",      # unterminated string literal
    'SELECT * FROM client WHERE $$',  # untokenizable

    # Not (yet) supported
    'SELECT * FROM client LIMIT 5',       # extra clause
    # Only columns may be selected, aliased or not
    "SELECT 'x' AS foo FROM client",      # aliased literal
    'SELECT * FROM (SELECT * FROM client) AS t',  # subquery is not a table
    'SELECT * FROM generate_series(1, 10)',  # table valued function not supported
    "INSERT INTO client VALUES ('x')",    # not a SELECT
    'SELECT * FROM client; SELECT * FROM client',  # multiple statements

    # Only UNION combines queries, and both sides must select the same columns
    'SELECT case_id FROM client INTERSECT SELECT visit_id FROM visit',
    'SELECT case_id FROM client EXCEPT SELECT visit_id FROM visit',
    'SELECT * FROM client UNION SELECT * FROM visit',  # 2 columns vs 3
    'SELECT case_id FROM client UNION SELECT visit_id FROM visit ORDER BY 1',
    'SELECT case_id FROM client UNION SELECT visit_id FROM visit LIMIT 5',
    'SELECT case_id FROM client UNION SELECT missing FROM visit',  # unknown column

    'SELECT * FROM unknown',              # unknown table
    'SELECT * FROM otherdomain.client',   # schema-qualified table
    'SELECT missing FROM client',         # unknown column
    'SELECT visit.name FROM client',      # qualified by a table not in the FROM
    "SELECT * FROM client WHERE name IS 'x'",       # IS with an unsupported operand
    'SELECT * FROM client WHERE name IS DISTINCT FROM NULL',  # IS DISTINCT FROM
    'SELECT DISTINCT ON () name FROM client',        # DISTINCT ON with no columns
    'SELECT name FROM client ORDER BY 1',           # ORDER BY an ordinal
    'SELECT name AS n FROM client ORDER BY n',      # ORDER BY a column alias
    'SELECT * FROM client WHERE case_id = -1',    # negative number
    "SELECT * FROM client WHERE name LIKE 'x%'",  # LIKE
    'SELECT * FROM client WHERE name IN ()',      # IN with no values
    'SELECT * FROM client WHERE name IN (SELECT name FROM client)',  # IN a subquery
    'SELECT * FROM client WHERE name',            # not a comparison
    "SELECT * FROM client WHERE LOWER(name) = 'x'",  # function call

    # Only `JOIN` and `LEFT JOIN` are supported for now.
    'SELECT * FROM client INNER JOIN visit ON client.case_id = visit.parent_id',
    'SELECT * FROM client LEFT OUTER JOIN visit ON client.case_id = visit.parent_id',
    'SELECT * FROM client RIGHT JOIN visit ON client.case_id = visit.parent_id',
    'SELECT * FROM client FULL JOIN visit ON client.case_id = visit.parent_id',
    'SELECT * FROM client CROSS JOIN visit',
    'SELECT * FROM client NATURAL JOIN visit',
    'SELECT * FROM client OUTER JOIN visit ON client.case_id = visit.parent_id',
    'SELECT * FROM client JOIN visit USING (case_id)',  # USING instead of ON
    'SELECT * FROM client JOIN visit',                  # no ON clause
    'SELECT * FROM client, visit',                      # comma join has no ON
    'SELECT * FROM client AS c JOIN visit ON c.case_id = visit.parent_id',  # alias
    'SELECT * FROM client JOIN client ON client.case_id = client.case_id',  # self join
    f'SELECT name {JOIN_SQL}',              # ambiguous, both tables have `name`
    f'SELECT client.visit_id {JOIN_SQL}',   # column belongs to the other table
])
def test_rejects_unsupported(sql):
    with pytest.raises(UnsupportedSQL):
        translate(sql, TABLES)


@pytest.mark.parametrize('alias, expected', [
    ('id', 'id'),
    ('"My Id"', '"My Id"'),
    # A column alias is the only user-supplied identifier that reaches the
    # generated SQL, so it must always come back out quoted and escaped.
    ('"a""b"', '"a""b"'),
    ('"a\'b"', '"a\'b"'),
    ('"); DROP TABLE client; --"', '"); DROP TABLE client; --"'),
    ('"select"', '"select"'),
])
def test_escapes_alias_identifiers(alias, expected):
    query = translate(f'SELECT case_id AS {alias} FROM client', TABLES)
    sql, params = _compiled(query)
    assert sql == f'SELECT client.case_id AS {expected} \nFROM client'
    assert params == {}


def test_handle_quoted_tables():
    hyphenated_table = table('hyphenated-table', column('case_id'))
    tables = {'hyphenated-table': hyphenated_table}
    result = translate('SELECT * FROM "hyphenated-table"', tables)
    assert str(result) == str(select([hyphenated_table]))
