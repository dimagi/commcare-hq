from django.template import Context, Template

import sqlalchemy
from sqlalchemy.schema import CreateIndex, CreateTable

from corehq.apps.project_db.table_ddl import (
    DomainSchema,
    get_project_db_engine,
)

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

Supported SQL:
 * SELECT of a column list or *, with optional AS aliases.
 * A single table in the FROM clause.
 * JOIN and LEFT JOIN, with an ON condition.
 * WHERE, combining conditions with AND, OR and NOT, and comparing columns and
   literals with =, <>, <, <=, >, >=, IS NULL/TRUE/FALSE and IN.
 * UNION and UNION ALL of the above.

Not supported:
 * Aggregates, function calls and arithmetic.
 * GROUP BY, ORDER BY, LIMIT, DISTINCT and LIKE.
 * Subqueries, CTEs and table aliases.

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
