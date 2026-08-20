import sqlalchemy
from sqlalchemy.schema import CreateIndex, CreateTable

from corehq.apps.project_db.table_ddl import (
    DomainSchema,
    get_project_db_engine,
)


def describe_project_db(domain):
    """Return the DDL of a domain's ProjectDB tables, annotated with row counts"""
    engine = get_project_db_engine()
    metadata = sqlalchemy.MetaData()
    metadata.reflect(bind=engine, schema=DomainSchema(domain).name)

    lines = [f"-- Project DB schema for domain: {domain}"]
    if not metadata.tables:
        lines.append(f"-- ERROR: No project DB tables found for domain '{domain}'")
    with engine.connect() as conn:
        for table in sorted(metadata.tables.values(), key=lambda t: t.name):
            row_count = conn.execute(
                sqlalchemy.select([sqlalchemy.func.count()]).select_from(table)
            ).scalar()
            ddl = str(CreateTable(table).compile(dialect=engine.dialect)).strip()
            lines.append(f"\n-- {row_count} rows")
            lines.append(f"{ddl};")
            for index in table.indexes:
                idx_ddl = str(CreateIndex(index).compile(dialect=engine.dialect)).strip()
                lines.append(f"{idx_ddl};")
    return '\n'.join(lines)
