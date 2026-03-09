from sqlalchemy import Boolean, Column, DateTime, Table, Text

from corehq.apps.userreports.util import get_table_name

PROJECT_DB_TABLE_PREFIX = 'projectdb_'


def get_project_db_table_name(domain, case_type):
    """Generate a PostgreSQL table name for a project DB case type table.

    Uses the same hashing/truncation strategy as UCR tables to ensure
    names are unique, deterministic, and within Postgres's 63-char limit.
    """
    return get_table_name(
        domain, case_type, max_length=63, prefix=PROJECT_DB_TABLE_PREFIX,
    )


def build_table_for_case_type(metadata, domain, case_type,
                              properties=None, relationships=None):
    """Build a SQLAlchemy Table for a case type with fixed case columns.

    :param metadata: SQLAlchemy MetaData instance
    :param domain: CommCare project domain
    :param case_type: case type name
    :param properties: reserved for future use (dynamic property columns)
    :param relationships: reserved for future use (relationship columns)
    :returns: SQLAlchemy Table
    """
    table_name = get_project_db_table_name(domain, case_type)
    return Table(
        table_name,
        metadata,
        Column('case_id', Text, primary_key=True),
        Column('owner_id', Text, nullable=False),
        Column('case_name', Text),
        Column('opened_on', DateTime(timezone=True)),
        Column('closed_on', DateTime(timezone=True)),
        Column('modified_on', DateTime(timezone=True)),
        Column('closed', Boolean),
        Column('external_id', Text),
        Column('server_modified_on', DateTime(timezone=True)),
    )
