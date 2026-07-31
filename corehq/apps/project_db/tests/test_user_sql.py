from decimal import Decimal

import pytest
from sqlalchemy import and_, column, literal, not_, or_, select, table

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
    ("SELECT * FROM client WHERE name = 'x'",
     select([CLIENT]).where(CLIENT.c.name == literal('x'))),
    ("SELECT * FROM client WHERE name <> 'x'",
     select([CLIENT]).where(CLIENT.c.name != literal('x'))),
    ('SELECT * FROM client WHERE case_id > 5',
     select([CLIENT]).where(CLIENT.c.case_id > literal(5))),
    ('SELECT * FROM client WHERE case_id <= 5.5',
     select([CLIENT]).where(CLIENT.c.case_id <= literal(Decimal('5.5')))),
    ("SELECT name FROM client WHERE case_id = 'c1'",
     select([CLIENT.c.name]).where(CLIENT.c.case_id == literal('c1'))),
    # Operands may appear in either order
    ("SELECT * FROM client WHERE 'x' = name",
     select([CLIENT]).where(literal('x') == CLIENT.c.name)),
    # Comparing two literals is pointless but harmless
    ('SELECT * FROM client WHERE 1 = 1',
     select([CLIENT]).where(literal(1) == literal(1))),

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
    'SELECT * FROM client LIMIT 5',       # extra clause
    'SELECT * FROM client, client',       # more than one table
    'SELECT * FROM (SELECT * FROM client) AS t',  # subquery is not a table
    'SELECT * FROM generate_series(1, 10)',  # table valued function not supported
    "INSERT INTO client VALUES ('x')",    # not a SELECT
    'SELECT * FROM client; SELECT * FROM client',  # multiple statements
    'SELECT * FROM unknown',              # unknown table
    'SELECT * FROM otherdomain.client',   # schema-qualified table
    'SELECT missing FROM client',         # unknown column
    'SELECT visit.name FROM client',      # qualified by a table not in the FROM
    'SELECT bogus.name FROM client',      # qualified by some other table
    "SELECT * FROM client WHERE name IS 'x'",       # IS with an unsupported operand
    'SELECT * FROM client WHERE name IS DISTINCT FROM NULL',  # IS DISTINCT FROM
    'SELECT * FROM client WHERE case_id = -1',    # negative number
    "SELECT * FROM client WHERE name LIKE 'x%'",  # LIKE
    'SELECT * FROM client WHERE name IN ()',      # IN with no values
    'SELECT * FROM client WHERE name IN (SELECT name FROM client)',  # IN a subquery
    'SELECT * FROM client WHERE name IN (missing)',  # unknown column in the values
    'SELECT * FROM client WHERE name',            # not a comparison
    "SELECT * FROM client WHERE missing = 'x'",   # unknown column
    "SELECT * FROM client WHERE LOWER(name) = 'x'",  # function call

    # Only `JOIN` and `LEFT JOIN` are supported for now
    'SELECT * FROM client INNER JOIN visit ON client.case_id = visit.parent_id',
    'SELECT * FROM client LEFT OUTER JOIN visit ON client.case_id = visit.parent_id',
    'SELECT * FROM client RIGHT JOIN visit ON client.case_id = visit.parent_id',
    'SELECT * FROM client RIGHT OUTER JOIN visit ON client.case_id = visit.parent_id',
    'SELECT * FROM client FULL JOIN visit ON client.case_id = visit.parent_id',
    'SELECT * FROM client FULL OUTER JOIN visit ON client.case_id = visit.parent_id',
    # Not valid SQL in any case: OUTER needs a side, INNER must not have one
    'SELECT * FROM client OUTER JOIN visit ON client.case_id = visit.parent_id',
    'SELECT * FROM client LEFT INNER JOIN visit ON client.case_id = visit.parent_id',
    'SELECT * FROM client CROSS JOIN visit',
    'SELECT * FROM client NATURAL JOIN visit',
    'SELECT * FROM client JOIN visit USING (case_id)',  # USING instead of ON
    'SELECT * FROM client JOIN visit',                  # no ON clause
    'SELECT * FROM client, visit',                      # comma join has no ON
    'SELECT * FROM client AS c JOIN visit ON c.case_id = visit.parent_id',  # alias
    'SELECT * FROM client JOIN client ON client.case_id = client.case_id',  # self join
    f'SELECT name {JOIN_SQL}',              # ambiguous, both tables have `name`
    f'SELECT unknown.name {JOIN_SQL}',      # unknown qualifier
    f'SELECT client.visit_id {JOIN_SQL}',   # column belongs to the other table
    f"SELECT * {JOIN_SQL} WHERE name = 'x'",  # ambiguous column in WHERE
])
def test_rejects_unsupported(sql):
    with pytest.raises(UnsupportedSQL):
        translate(sql, TABLES)


def test_handle_quoted_tables():
    hyphenated_table = table('hyphenated-table', column('case_id'))
    tables = {'hyphenated-table': hyphenated_table}
    result = translate('SELECT * FROM "hyphenated-table"', tables)
    assert str(result) == str(select([hyphenated_table]))
