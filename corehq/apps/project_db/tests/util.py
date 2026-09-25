from contextlib import contextmanager
from unittest.mock import patch

from unmagic import fixture

from corehq.apps.project_db.table_ddl import (
    CaseTable,
    DomainSchema,
    create_or_update_project_db,
    get_project_db_engine,
)
from corehq.apps.project_db.user_sql import UserSQL


@fixture
def utc_project():
    """Mock out Domain object query for timezone"""
    with patch.object(UserSQL, 'timezone', 'UTC'):
        yield


@contextmanager
def project_db_table(domain, case_type, properties, data=None):
    """Pytest fixture to construct a ProjectDB table

    :param data: (columns, rows) tuple
    """
    with patch('corehq.apps.project_db.table_ddl._get_case_types', return_value=[case_type]), \
         patch.object(CaseTable, '_get_dd_properties', return_value=properties.items()):
        create_or_update_project_db(domain)
    try:
        if data:
            columns, raw_rows = data
            rows = [dict(zip(columns, r)) for r in raw_rows]
            table = CaseTable(domain, case_type).reflect()
            with get_project_db_engine().begin() as conn:
                conn.execute(table.insert(), rows)
        yield
    finally:
        with get_project_db_engine().begin() as conn:
            DomainSchema(domain).drop(conn)
