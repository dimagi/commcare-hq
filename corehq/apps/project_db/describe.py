from django.template import Context, Template

import sqlalchemy
from sqlalchemy.schema import CreateIndex, CreateTable

from corehq.apps.project_db.table_ddl import (
    DomainSchema,
    get_project_db_engine,
)

DESCRIPTION_TEMPLATE = """\
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
        return "ERROR: No project DB tables found for domain '{{ domain }}'"

    with engine.connect() as conn:
        context = {
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
