import sqlalchemy
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
