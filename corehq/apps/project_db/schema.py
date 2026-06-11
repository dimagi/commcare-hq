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
