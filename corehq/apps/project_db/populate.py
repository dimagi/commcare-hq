import datetime
from collections import defaultdict

from sqlalchemy import bindparam, func
from sqlalchemy.dialects.postgresql import insert

from dimagi.utils.chunked import chunked

from corehq.apps.data_dictionary.models import CaseProperty
from corehq.util.metrics import metrics_histogram_timer

from .table_ddl import CaseTable, get_project_db_engine, property_column


def send_cases_to_project_db(domain, cases):
    """Bulk upsert CommCareCases"""
    metric = 'commcare.project_db.populate.duration'
    with metrics_histogram_timer(metric, timing_buckets=(.1, .5, 1, 2, 5), tags={'domain': domain}):
        cases_by_type = defaultdict(list)
        for case in cases:
            cases_by_type[case.type].append(case)
        for case_type, case_type_cases in cases_by_type.items():
            populate_case_type(domain, case_type, case_type_cases)


def populate_case_type(domain, case_type, cases):
    """Chunked upsert CommCareCases of a single case type"""
    engine = get_project_db_engine()
    table = CaseTable(domain, case_type).reflect()
    if table is not None:
        for chunk in chunked(cases, 1000):
            if not all(c.type == case_type for c in chunk):
                raise ValueError(f'All cases must be of type {case_type}')

            with engine.begin() as conn:
                upsert_cases(conn, table, chunk)


def upsert_cases(conn, table, cases):
    """Insert or update cases into a project DB table"""
    stmt = insert(table).values(_insert_values(table))
    stmt = stmt.on_conflict_do_update(
        index_elements=['case_id'],
        set_={col: stmt.excluded[col] for col in table.c.keys() if col != 'case_id'},
    )
    rows = [case_to_row(case, table.c) for case in cases]
    conn.execute(stmt, rows)


def _insert_values(table):
    """Specify what values to insert and how"""
    # Raw values
    values = {col.name: bindparam(col.name, type_=col.type) for col in table.c}
    # Values that are coerced to type in SQL
    for col in table.c:
        for data_type, coerce in _SQL_COERCIONS:
            if col.comment and col.name == property_column(col.comment, data_type):
                values[col.name] = coerce(values[property_column(col.comment)])
    return values


def case_to_row(case, columns):
    """Map case to table column names for insertion"""
    ids_by_identifier = {idx.identifier: idx.referenced_id for idx in case.live_indices}
    row = {  # Mirrors CaseTable._static_columns
        'case_id': case.case_id,
        'owner_id': case.owner_id,
        'case_name': case.name,
        'opened_on': _as_utc(case.opened_on),
        'closed_on': _as_utc(case.closed_on),
        'modified_on': _as_utc(case.modified_on),
        'closed': case.closed,
        'external_id': case.external_id or '',
        'server_modified_on': _as_utc(case.server_modified_on),
        'parent_id': ids_by_identifier.get('parent'),
        'host_id': ids_by_identifier.get('host'),
    }
    for column in columns:
        if column.name.startswith('prop__'):
            value = case.case_json.get(column.comment)
            row[column.name] = '' if value is None else str(value)
    return row


def _as_utc(value):
    """Attach explicit UTC timezone to naive datetime values"""
    return value.replace(tzinfo=datetime.timezone.utc) if value else None


# Functions defined in lib_projectdb.sql
_SQL_COERCIONS = [
    (CaseProperty.DataType.DATE, func.lib_projectdb.coerce_to_date),
    (CaseProperty.DataType.NUMBER, func.lib_projectdb.coerce_to_number),
    (CaseProperty.DataType.SELECT, func.lib_projectdb.coerce_to_array),
    (CaseProperty.DataType.GPS, func.lib_projectdb.coerce_to_gps),
]
