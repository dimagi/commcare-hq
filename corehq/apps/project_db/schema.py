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
