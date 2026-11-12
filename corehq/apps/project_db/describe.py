from django.template import Context, Template

import sqlalchemy
from sqlalchemy.schema import CreateIndex, CreateTable

from corehq.apps.project_db.table_ddl import (
    DomainSchema,
    get_project_db_engine,
)

# This text is for people who know SQL well - it describes the specifics of
# this constrained environment, and should not have general guidance on writing
# correct or performant SQL
DESCRIPTION_TEMPLATE = """\
This is the ProjectDB for {{ domain }}: relational, schema'd tables of the
project's case data, generated automatically from the data dictionary.

The SQL you pass in will be parsed and rebuilt, with only a limited subset of
functionality available.

Schema:
 * Every table has the same case metadata columns.
 * Each case property has a prop__<name> text column holding its raw value.
 * Properties with a declared type also have a parallel typed column
   (date_prop__, number_prop__, select_prop__, gps_prop__) holding the coerced
   value, or NULL where the raw text could not be coerced.
 * select_prop columns use an empty array instead of NULL.
 * prop__ columns are not nullable; unset properties are stored as the empty string.
 * Cases link to each other through parent_id and host_id, which hold the
   case_id of a case in another table.
 * Datetime columns carry a timezone, and will be queried in the project timezone

Supported SQL:
 * SELECT of *, or a list of values and aggregates, with optional AS aliases.
 * DISTINCT, and DISTINCT ON (columns or SELECT aliases).
 * A single table or CTE in the FROM clause, with an optional alias.
 * JOIN (or INNER JOIN) and LEFT JOIN (or LEFT OUTER JOIN), with an ON
   condition.
 * WHERE with a condition.
 * GROUP BY columns or aliases, and HAVING.
 * Aggregates: count(*), count(value), sum, avg, min, max, array_agg(value)
   and string_agg(value, '<delimiter>'). Each may take DISTINCT and
   FILTER (WHERE condition).
 * ORDER BY a column or a SELECT alias, with ASC/DESC and NULLS FIRST/LAST.
   To sort by an aggregate or other value, give it an alias and order by that.
 * UNION and UNION ALL of the above.
 * WITH CTEs, only at the top level of the query. A CTE the query never
   references is dropped, along with any parameters in it.
 * Values: columns, literals, and named :parameters wherever a literal is
   allowed, plus:
   - now() for the current time and today() for the current date. Dates and
     times resolve in the project's timezone, and a date or time literal is
     read in that same timezone, so '2026-01-01' means midnight there.
   - make_interval(days => 30), added to or subtracted from a date or time,
     as in opened_on > now() - make_interval(months => 3). Its units are
     years, months, weeks, days, hours, mins and secs, and a count may be a
     parameter or integer literal.
   - string_to_array(value, '<delimiter>'), which splits text into an array
     to compare against select_prop__ columns. The delimiter must be a
     literal, so a parameter holding 'fever cough' is written
     string_to_array(:symptoms, ' ').
 * Conditions, combined with AND, OR, NOT and parentheses:
   - Comparisons between values: =, <>, <, <=, >, >=
   - IS [NOT] NULL, IS [NOT] TRUE, IS [NOT] FALSE
   - IN (a, b, ...) or IN :parameter
   - IN (SELECT ...), where the subquery may not reference the outer query.
   - LIKE and ILIKE, with % and _ pattern support.
   - A boolean column on its own, as in WHERE NOT closed
   - Array containment against an ARRAY['a', 'b'] literal, for select_prop__
     columns: @> holds all of these, <@ holds only these, && holds any of
     these.
   - within_distance(gps_prop__ column, '<latitude> <longitude>', distance,
     unit), which matches cases within that distance of the point. The unit
     is optional and defaults to 'meters'. It may be 'meters', 'kilometers',
     'miles', 'yards', 'feet' or 'nauticalmiles', and must be a literal.
   - Name matching, comparing two values case-insensitively:
     sounds_like(a, b) matches by pronunciation (Smith/Smyth, Brown/Braun),
     fuzzy_match(a, b) by spelling (Michael/Micheal, Robert/Roberto), and
     similar_name(a, b) matches if either does.

Not supported:
 * Other function calls and casts (::type).
 * ORDER BY inside an aggregate.
 * Arithmetic, apart from shifting a date or time by an interval.
 * INTERVAL literals, such as INTERVAL '30 days'. Use make_interval() instead.
 * LIMIT, BETWEEN, SIMILAR TO, and LIKE with ESCAPE or ANY.
 * Negative numbers.
 * Subqueries other than IN (SELECT ...).
 * WITH RECURSIVE, [NOT] MATERIALIZED, and column aliases on a CTE.
 * INTERSECT and EXCEPT.
 * ORDER BY on a UNION.
 * RIGHT, FULL and CROSS JOIN. Write a RIGHT JOIN as a LEFT JOIN with the
   tables swapped.

This project has the following tables:
{% for summary in table_summaries %}\
 * {{ summary }}
{% endfor %}\

Here is a SQL description of the tables:

{% for statement in table_definitions %}\
{{ statement }};
{% endfor %}\
"""


def describe_project_db(domain):
    """Return the DDL of a domain's ProjectDB tables, annotated with row counts"""
    engine = get_project_db_engine()
    metadata = sqlalchemy.MetaData()
    metadata.reflect(bind=engine, schema=DomainSchema(domain).name)
    tables = sorted(metadata.tables.values(), key=lambda t: t.name)
    if not tables:
        return f"ERROR: No project DB tables found for domain '{domain}'"

    with engine.connect() as conn:
        context = {
            'domain': domain,
            'table_summaries': list(_table_summaries(tables, conn)),
            'table_definitions': list(_table_definitions(tables, engine)),
        }
    return Template(DESCRIPTION_TEMPLATE).render(Context(context, autoescape=False))


def _table_summaries(tables, conn):
    for table in tables:
        row_count = conn.execute(
            sqlalchemy.select([sqlalchemy.func.count()]).select_from(table)
        ).scalar()
        yield f"{table.name} - {row_count} rows"


def _table_definitions(tables, engine):
    # Copying to a schema-less MetaData drops the schema qualifier from the DDL
    unqualified = sqlalchemy.MetaData()
    for table in tables:
        table = table.tometadata(unqualified, schema=None)
        yield _compile_ddl(CreateTable(table), engine)
        for index in table.indexes:
            yield _compile_ddl(CreateIndex(index), engine)


def _compile_ddl(statement, engine):
    return str(statement.compile(dialect=engine.dialect)).strip()
