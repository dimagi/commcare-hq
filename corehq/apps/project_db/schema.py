import sqlalchemy
from sqlalchemy import Boolean, Column, DateTime, Index, Table, Text
from sqlalchemy.dialects import postgresql

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
    STATIC_COLUMNS = (
        # (name, type, column_kwargs).
        ('case_id', Text, {'primary_key': True}),
        ('owner_id', Text, {'nullable': False}),
        ('case_name', Text, {}),
        ('opened_on', DateTime, {}),
        ('closed_on', DateTime, {}),
        ('modified_on', DateTime, {}),
        ('closed', Boolean, {}),
        ('external_id', Text, {}),
        ('server_modified_on', DateTime, {}),
        ('parent_id', Text, {}),
        ('host_id', Text, {}),
    )

    def __init__(self, domain, case_type):
        self.domain = domain
        self.case_type = case_type  # TODO truncate and append hash if needed
        self.domain_schema = DomainSchema(domain)

    def build_definition(self, metadata):
        """Build a SQLAlchemy Table object defining the case type table"""
        static_columns = [Column(name, col_type, **kwargs)
                         for name, col_type, kwargs in self.STATIC_COLUMNS]
        table = Table(
            self.case_type,
            metadata,  # The table is also attached to the provided metadata
            *static_columns,
            schema=self.domain_schema.name,
        )
        Index(f'ix_{self.case_type}_owner_id', table.c['owner_id'])
        Index(f'ix_{self.case_type}_modified_on', table.c['modified_on'])
        Index(f'ix_{self.case_type}_parent_id', table.c['parent_id'])
        Index(f'ix_{self.case_type}_host_id', table.c['host_id'])
        return table
