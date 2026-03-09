import sqlalchemy
from sqlalchemy import inspect

from corehq.sql_db.connections import connection_manager, DEFAULT_ENGINE_ID


def get_project_db_engine():
    """Return a SQLAlchemy engine for project DB tables.

    Currently uses the default Django database. This will later switch
    to a dedicated ``'project_db'`` engine ID.
    """
    return connection_manager.get_engine(DEFAULT_ENGINE_ID)


def create_tables(engine, metadata):
    """Create all tables in ``metadata`` that don't yet exist.

    Uses ``checkfirst=True`` so existing tables are left untouched.
    """
    metadata.create_all(bind=engine, checkfirst=True)


def evolve_table(engine, table):
    """Add columns and indexes present in ``table`` but missing from the database.

    This is append-only: columns and indexes that exist in the database
    but not in ``table`` are left in place (never dropped).
    """
    inspector = inspect(engine)
    existing_columns = {col['name'] for col in inspector.get_columns(table.name)}
    new_columns = [col for col in table.columns if col.name not in existing_columns]

    existing_indexes = {
        idx['name'] for idx in inspector.get_indexes(table.name)
    }
    new_indexes = [
        idx for idx in table.indexes if idx.name not in existing_indexes
    ]

    if not new_columns and not new_indexes:
        return

    with engine.begin() as conn:
        for column in new_columns:
            col_type = column.type.compile(dialect=engine.dialect)
            conn.execute(sqlalchemy.text(
                f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'
            ))
        for index in new_indexes:
            col_names = ', '.join(f'"{col.name}"' for col in index.columns)
            conn.execute(sqlalchemy.text(
                f'CREATE INDEX "{index.name}" ON "{table.name}" ({col_names})'
            ))
