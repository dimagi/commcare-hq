"""Turn project DB query results into cases."""
from sqlalchemy.sql.selectable import CompoundSelect

from corehq.apps.project_db.user_sql import UnsupportedSQL

CASE_ID_COLUMN = 'case_id'


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
