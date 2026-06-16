from contextlib import contextmanager
from unittest.mock import patch

from corehq.apps.project_db.table_ddl import (
    CaseTable,
    DomainSchema,
    create_or_update_project_db,
    get_project_db_engine,
)


@contextmanager
def project_db_table(domain, case_type, properties):
    """Pytest fixture to construct a ProjectDB table"""
    with patch('corehq.apps.project_db.table_ddl._get_case_types', return_value=[case_type]), \
         patch.object(CaseTable, '_get_dd_properties', return_value=properties.items()):
        create_or_update_project_db(domain)
    try:
        yield
    finally:
        with get_project_db_engine().begin() as conn:
            DomainSchema(domain).drop(conn)
