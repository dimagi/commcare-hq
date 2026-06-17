import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.dialects.postgresql import insert

from dimagi.utils.chunked import chunked

from corehq.apps.data_dictionary.models import CaseProperty

from .table_ddl import CaseTable, get_project_db_engine


def send_to_project_db(domain, case_type, cases):
    """Bulk upsert CommCareCases of a single case type"""
    engine = get_project_db_engine()
    table = CaseTable(domain, case_type).reflect()
    if table is not None:
        for chunk in chunked(cases, 1000):
            if not all(c.type == case_type for c in chunk):
                raise ValueError(f'All cases much be of type {case_type}')

            with engine.begin() as conn:
                upsert_cases(conn, table, chunk)


def upsert_cases(conn, table, cases):
    """Insert or update cases into a project DB table"""
    columns = table.c.keys()
    rows = [case_to_row(case, columns) for case in cases]
    # Make sure every column is specified
    rows = [{col: row.get(col, None) for col in columns}
            for row in rows]
    stmt = insert(table)
    stmt = stmt.on_conflict_do_update(
        index_elements=['case_id'],
        set_={col: stmt.excluded[col] for col in columns if col != 'case_id'},
    )
    conn.execute(stmt, rows)


def case_to_row(case, table_columns):
    """Map case to table column names for insertion"""
    ids_by_identifier = {idx.identifier: idx.referenced_id for idx in case.live_indices}
    row = {  # Mirrors CaseTable._static_columns
        'case_id': case.case_id,
        'owner_id': case.owner_id,
        'case_name': case.name,
        'opened_on': case.opened_on,
        'closed_on': case.closed_on,
        'modified_on': case.modified_on,
        'closed': case.closed,
        'external_id': case.external_id,
        'server_modified_on': case.server_modified_on,
        'parent_id': ids_by_identifier.get('parent'),
        'host_id': ids_by_identifier.get('host'),
    }
    for key, value in case.case_json.items():
        col_name = f'prop__{key}'
        if col_name in table_columns:
            row[col_name] = str(value)
            for suffix, coerce_fn in _TYPED_COERCIONS:
                typed_col = f'{col_name}__{suffix}'
                if typed_col in table_columns:
                    row[typed_col] = coerce_fn(value)
    return row


def coerce_to_date(value):
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value[:10])
    except (ValueError, TypeError):
        return None


def coerce_to_number(value):
    if not value or not str(value).strip():
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None


# Parallels CaseTable.COERCED_PROPERTY_TYPES
_TYPED_COERCIONS = [
    (CaseProperty.DataType.DATE, coerce_to_date),
    (CaseProperty.DataType.NUMBER, coerce_to_number),
]
