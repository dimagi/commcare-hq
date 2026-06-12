import sqlalchemy
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Boolean, Column, Date, DateTime, Numeric, Table, Text
from sqlalchemy.dialects import postgresql

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.sql_db.connections import PROJECT_DB_ENGINE_ID, connection_manager


def get_project_db_engine():
    """Return a SQLAlchemy engine for project DB tables"""
    return connection_manager.get_engine(PROJECT_DB_ENGINE_ID)


class DomainSchema:
    """A PostgreSQL schema that stores a domain's ProjectDB tables"""
    def __init__(self, domain):
        self.domain = domain

    @property
    def name(self):
        return f'projectdb_{self.domain}'

    @property
    def _quoted_name(self):
        return postgresql.dialect().identifier_preparer.quote(self.name)

    def create(self, conn):
        conn.execute(sqlalchemy.text(
            f'CREATE SCHEMA IF NOT EXISTS {self._quoted_name}'
        ))

    def set_local_search_path(self, conn):
        """Scope the connection's search_path to a domain's project DB schema"""
        conn.execute(sqlalchemy.text(
            f'SET LOCAL search_path TO {self._quoted_name}'
        ))

    def drop(self, conn):
        conn.execute(sqlalchemy.text(
            f'DROP SCHEMA IF EXISTS {self._quoted_name} CASCADE'
        ))


class CaseTable:
    COERCED_PROPERTY_TYPES = {
        # CaseProperty data_type to SQLAlchemy column type
        CaseProperty.DataType.DATE: Date,
        CaseProperty.DataType.NUMBER: Numeric,
    }

    def __init__(self, domain, case_type):
        self.domain = domain
        self.case_type = case_type  # TODO truncate and append hash if needed
        self.domain_schema = DomainSchema(domain)

    def build_definition(self, metadata):
        """Build a SQLAlchemy Table object defining the case type table"""
        return Table(
            self.case_type,
            metadata,  # The table is also attached to the provided metadata
            *self._build_property_columns(),
            *self._static_columns(),
            schema=self.domain_schema.name,
        )

    def _build_property_columns(self):
        """Build Column objects for dynamic case properties.

        Every property gets a raw Text column named
        ``prop__<name>``. Some typed properties get an additional
        typed column.
        """
        for name, data_type in self._get_dd_properties():
            col_name = f'prop__{name}'
            yield Column(col_name, Text)

            if col_type := self.COERCED_PROPERTY_TYPES.get(data_type):
                yield Column(f'{col_name}__{data_type}', col_type)

    def _get_dd_properties(self):
        return CaseProperty.objects.filter(
            case_type__domain=self.domain,
            case_type__name=self.case_type,
            case_type__is_deprecated=False,
            deprecated=False,
        ).values_list('name', 'data_type')

    @staticmethod
    def _static_columns():
        return [
            Column('case_id', Text, primary_key=True),
            Column('owner_id', Text, nullable=False, index=True),
            Column('case_name', Text),
            Column('opened_on', DateTime),
            Column('closed_on', DateTime),
            Column('modified_on', DateTime),
            Column('closed', Boolean),
            Column('external_id', Text),
            Column('server_modified_on', DateTime),
            Column('parent_id', Text, index=True),
            Column('host_id', Text, index=True),
        ]


def create_or_update_project_db(domain):
    metadata = sqlalchemy.MetaData()

    case_types = _get_case_types(domain)
    if not case_types:
        return
    case_tables = [
        CaseTable(domain, case_type).build_definition(metadata)
        for case_type in case_types
    ]

    engine = get_project_db_engine()
    with engine.begin() as conn:
        DomainSchema(domain).create(conn)
        metadata.create_all(bind=conn, checkfirst=True)
        for table in case_tables:
            update_table(conn, table)


def _get_case_types(domain):
    return list(CaseType.objects.filter(
        domain=domain, is_deprecated=False,
    ).values_list('name', flat=True))


def update_table(conn, table):
    """Add columns and indexes present in ``table`` but missing from the database.

    This is append-only: columns and indexes that exist in the database
    but not in ``table`` are left in place (never dropped).
    """
    inspector = sqlalchemy.inspect(conn)
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

    op = Operations(MigrationContext.configure(conn))
    for column in new_columns:
        # Detach column from its table so Alembic can re-parent it
        detached_col = column.copy()
        detached_col.table = None
        op.add_column(table.name, detached_col, schema=schema)
    for index in new_indexes:
        index.create(bind=conn)
