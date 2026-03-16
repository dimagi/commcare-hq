import sqlalchemy
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Boolean, Column, Date, DateTime, Index, Numeric, Table, Text, inspect

from corehq.sql_db.connections import DEFAULT_ENGINE_ID, connection_manager

# Columns present on every project DB table, in order.
# Each entry is (name, type, column_kwargs).
FIXED_COLUMNS = (
    ('case_id', Text, {'primary_key': True}),
    ('owner_id', Text, {'nullable': False}),
    ('case_name', Text, {}),
    ('opened_on', DateTime(timezone=True), {}),
    ('closed_on', DateTime(timezone=True), {}),
    ('modified_on', DateTime(timezone=True), {}),
    ('closed', Boolean, {}),
    ('external_id', Text, {}),
    ('server_modified_on', DateTime(timezone=True), {}),
    ('parent_id', Text, {}),
    ('host_id', Text, {}),
)

FIXED_COLUMN_NAMES = frozenset(name for name, _, _ in FIXED_COLUMNS)


def get_schema_name(domain):
    """Return the PostgreSQL schema name for a domain's project DB tables."""
    return f'projectdb_{domain}'


def get_case_table_schema(domain, case_type):
    """Construct a SQLAlchemy ``Table`` schema by reflection

    This inspects the DB to get the schema for a case type table in the ProjectDB
    """
    try:
        return Table(
            case_type,
            sqlalchemy.MetaData(),
            schema=get_schema_name(domain),
            autoload=True,
            autoload_with=get_project_db_engine(),
        )
    except sqlalchemy.exc.NoSuchTableError:
        return None


def build_all_table_schemas(domain, metadata=None):
    """Build SQLAlchemy Tables for all active case types in a domain.

    Reads the data dictionary (CaseType and CaseProperty models) and
    produces a corresponding SQLAlchemy Table for each non-deprecated
    case type.

    :param domain: CommCare project domain
    :param metadata: optional SQLAlchemy MetaData instance
    :returns: dict mapping case type name to SQLAlchemy Table
    """
    from corehq.apps.data_dictionary.models import CaseProperty, CaseType
    if metadata is None:
        metadata = sqlalchemy.MetaData()

    case_types = CaseType.objects.filter(
        domain=domain, is_deprecated=False,
    )

    tables = {}
    for case_type in case_types:
        properties = list(
            CaseProperty.objects.filter(
                case_type=case_type, deprecated=False,
            ).values_list('name', 'data_type')
        )
        tables[case_type.name] = build_table_schema(
            domain, case_type.name,
            metadata=metadata,
            properties=properties,
        )

    return tables


def build_table_schema(domain, case_type, metadata=None, properties=None):
    """Build a SQLAlchemy Table for a case type with fixed case columns.

    The table is placed in the domain's project DB schema
    (``projectdb_<domain>``), with the case type name as the table name.

    :param domain: CommCare project domain
    :param case_type: case type name
    :param metadata: optional SQLAlchemy MetaData instance
    :param properties: list of (name, data_type) tuples for dynamic columns
    :returns: SQLAlchemy Table
    """
    if metadata is None:
        metadata = sqlalchemy.MetaData()
    property_columns = _build_property_columns(properties or [])
    fixed_columns = [Column(name, col_type, **kwargs)
                     for name, col_type, kwargs in FIXED_COLUMNS]
    table = Table(
        case_type,
        metadata,
        *fixed_columns,
        *property_columns,
        schema=get_schema_name(domain),
    )
    Index(f'ix_{case_type}_owner_id', table.c['owner_id'])
    Index(f'ix_{case_type}_modified_on', table.c['modified_on'])
    Index(f'ix_{case_type}_parent_id', table.c['parent_id'])
    Index(f'ix_{case_type}_host_id', table.c['host_id'])
    return table


# --- Private helpers ---

# Maps data types that get an additional typed column to their
# (SQLAlchemy type, column name suffix) pairs.
# These keys must match CaseProperty.DataType enum values
# from corehq/apps/data_dictionary/models.py.
SEP = '__'

_TYPED_COLUMN_EXTRAS = {
    'date': (Date, 'date'),
    'number': (Numeric, 'numeric'),
}


def _build_property_columns(properties):
    """Build Column objects for dynamic case properties.

    Every property gets a raw Text column named ``prop__<name>``.
    ``date`` and ``number`` properties get an additional typed column.
    """
    columns = []
    for name, data_type in properties:
        col_name = f'prop{SEP}{name}'
        columns.append(Column(col_name, Text))
        if data_type in _TYPED_COLUMN_EXTRAS:
            sa_type, suffix = _TYPED_COLUMN_EXTRAS[data_type]
            columns.append(Column(f'{col_name}{SEP}{suffix}', sa_type))
    return columns


# --- Engine and DDL management ---


def sync_domain_tables(engine, domain):
    """Ensure project DB tables for a domain exist and match the data dictionary.

    Creates the schema and any missing tables, then evolves existing
    tables to add new columns and indexes.

    :returns: dict mapping case type name to SQLAlchemy Table
    """
    tables = build_all_table_schemas(domain)
    if not tables:
        return tables
    metadata = next(iter(tables.values())).metadata
    create_tables(engine, metadata)
    for table in tables.values():
        evolve_table(engine, table)
    return tables


def get_project_db_engine():
    """Return a SQLAlchemy engine for project DB tables.

    Currently uses the default Django database. This will later switch
    to a dedicated ``'project_db'`` engine ID.
    """
    return connection_manager.get_engine(DEFAULT_ENGINE_ID)


def create_tables(engine, metadata):
    """Create all tables in ``metadata`` that don't yet exist"""
    schemas = {t.schema for t in metadata.tables.values() if t.schema}
    with engine.begin() as conn:
        # First create any schemas referenced by the tables
        for schema in schemas:
            conn.execute(sqlalchemy.text(
                f'CREATE SCHEMA IF NOT EXISTS "{schema}"'
            ))
    # checkfirst=True ensures existing tables are left untouched.
    metadata.create_all(bind=engine, checkfirst=True)


def evolve_table(engine, table):
    """Add columns and indexes present in ``table`` but missing from the database.

    This is append-only: columns and indexes that exist in the database
    but not in ``table`` are left in place (never dropped).
    """
    inspector = inspect(engine)
    schema = table.schema
    existing_columns = {
        col['name'] for col in inspector.get_columns(table.name, schema=schema)
    }
    new_columns = [col for col in table.columns if col.name not in existing_columns]

    existing_indexes = {
        idx['name'] for idx in inspector.get_indexes(table.name, schema=schema)
    }
    new_indexes = [idx for idx in table.indexes if idx.name not in existing_indexes]

    if not new_columns and not new_indexes:
        return

    with engine.begin() as conn:
        op = Operations(MigrationContext.configure(conn))
        for column in new_columns:
            col = column.copy()
            col.table = None
            op.add_column(table.name, col, schema=schema)
        for index in new_indexes:
            index.create(bind=conn)
