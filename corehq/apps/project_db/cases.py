"""Turn project DB query results into cases."""
from sqlalchemy.sql.selectable import CompoundSelect

from corehq.apps.project_db.user_sql import UnsupportedSQL

CASE_ID_COLUMN = 'case_id'
PROPERTY_PREFIX = 'prop__'

#: Project DB column name to ``CommCareCase`` attribute
_CASE_COLUMNS = {
    'case_id': 'case_id',
    'case_name': 'name',
    'owner_id': 'owner_id',
    'opened_on': 'opened_on',
    'closed_on': 'closed_on',
    'closed': 'closed',
    'modified_on': 'modified_on',
    'server_modified_on': 'server_modified_on',
    'external_id': 'external_id',
}


def rows_to_cases(rows, domain, table):
    """Build cases from project DB rows, using only the columns selected.

    Attributes whose column was not selected are left unset, so a query may
    project fewer columns to return a smaller case.
    """
    from corehq.form_processor.models import CommCareCase

    property_columns = [col for col in table.columns
                        if col.name.startswith(PROPERTY_PREFIX)]
    cases = []
    for row in rows:
        present = set(row.keys())
        cases.append(CommCareCase(
            domain=domain,
            # The comment holds the raw case type, which the table name may
            # have truncated
            type=table.comment,
            # Project DB has no index metadata. Setting this explicitly keeps
            # CaseDBXMLGenerator.add_indices off the database, rather than
            # relying on an unsaved case happening to return no indices.
            indices=[],
            case_json={col.comment: row[col.name] for col in property_columns
                       if col.name in present and row[col.name]},
            **{attribute: row[name] for name, attribute in _CASE_COLUMNS.items()
               if name in present},
        ))
    return cases


def get_case_id_column(query):
    """Return the column holding the case id in a translated query.

    A query that feeds case search has to say which of its columns is the
    case. Exactly one may be named ``case_id``: SQLAlchemy's ``.c``
    collection collapses duplicate names, so two ``case_id`` columns in a
    join would silently resolve to whichever was selected last.
    """
    if isinstance(query, CompoundSelect):
        columns = [col for leg in query.selects for col in leg.inner_columns]
    else:
        columns = list(query.inner_columns)
    matches = [col for col in columns
               if getattr(col, 'name', None) == CASE_ID_COLUMN]
    if not matches:
        raise UnsupportedSQL(f"one column must be named '{CASE_ID_COLUMN}'")
    # One table, so the results have one case type and one set of property
    # columns. This also rules out a UNION whose legs are different case
    # types, which would have neither.
    tables = {col.table.name for col in matches}
    if len(tables) > 1:
        raise UnsupportedSQL(
            f"ambiguous column: '{CASE_ID_COLUMN}' is selected from "
            + ' and '.join(sorted(tables))
        )
    return matches[-1]
