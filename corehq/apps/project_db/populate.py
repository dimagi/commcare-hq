import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.dialects.postgresql import insert

from corehq.apps.project_db.schema import SEP

FIXED_COLUMNS = {
    'case_id', 'owner_id', 'case_name', 'opened_on', 'closed_on',
    'modified_on', 'closed', 'external_id', 'server_modified_on',
    'parent_id', 'host_id',
}

PROPERTY_PREFIX = 'prop.'


def upsert_case(engine, table, case_data):
    """Insert or update a single case row in a project DB table.

    ``case_data`` is a dict with:
    - Fixed field keys (``case_id``, ``owner_id``, etc.) passed through directly
    - Dynamic properties namespaced as ``prop.<name>`` (mapped to ``prop__<name>`` columns)

    On conflict on ``case_id``, only the columns present in ``case_data``
    are updated — columns not included in the dict are left unchanged.
    Callers should include all fields for a full upsert.
    """
    table_columns = set(table.c.keys())
    values = _build_values_dict(case_data, table_columns)

    stmt = insert(table).values(**values)
    update_dict = {k: v for k, v in values.items() if k != 'case_id'}
    stmt = stmt.on_conflict_do_update(
        index_elements=['case_id'],
        set_=update_dict,
    )

    with engine.begin() as conn:
        conn.execute(stmt)


def case_to_row_dict(case):
    """Convert a CommCareCase instance to a dict suitable for ``upsert_case``.

    Extracts fixed fields, dynamic properties (namespaced under
    ``prop.``) from ``case_json``, and ``parent_id``/``host_id``
    from ``live_indices``.
    """
    row = {
        'case_id': case.case_id,
        'owner_id': case.owner_id,
        'case_name': case.name,
        'opened_on': case.opened_on,
        'closed_on': case.closed_on,
        'modified_on': case.modified_on,
        'closed': case.closed,
        'external_id': case.external_id,
        'server_modified_on': case.server_modified_on,
        'parent_id': _get_index_ref(case, 'parent'),
        'host_id': _get_index_ref(case, 'host'),
    }
    for key, value in case.case_json.items():
        row[f'{PROPERTY_PREFIX}{key}'] = value
    return row


def coerce_to_date(value):
    """Parse a date string, returning a ``datetime.date`` or ``None``.

    Accepts ISO format: ``YYYY-MM-DD`` or ``YYYY-MM-DDTHH:MM:SS``.
    Returns ``None`` for invalid, empty, or ``None`` input.
    """
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value[:10])
    except (ValueError, TypeError):
        return None


def coerce_to_number(value):
    """Parse a numeric string, returning a ``Decimal`` or ``None``.

    Returns ``None`` for invalid, empty, or ``None`` input.
    """
    if not value or not str(value).strip():
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None


# --- Private helpers ---

# Maps typed column suffixes to their coercion functions.
_TYPED_COERCIONS = {
    'date': coerce_to_date,
    'numeric': coerce_to_number,
}


def _build_values_dict(case_data, table_columns):
    """Map case_data keys to table column names, skipping unknown columns.

    Keys are expected in two forms:
    - Fixed fields: bare names like ``case_id``, ``owner_id``
    - Properties: namespaced as ``prop.<name>``, mapped to ``prop__<name>`` columns
    """
    values = {}
    for key, value in case_data.items():
        if key.startswith(PROPERTY_PREFIX):
            prop_name = key[len(PROPERTY_PREFIX):]
            col_name = f'prop{SEP}{prop_name}'
            if col_name in table_columns:
                values[col_name] = value
                _set_typed_columns(values, col_name, value, table_columns)
        elif key in FIXED_COLUMNS:
            values[key] = value
    return values


def _set_typed_columns(values, col_name, raw_value, table_columns):
    """If typed companion columns exist, coerce and set their values."""
    for suffix, coerce_fn in _TYPED_COERCIONS.items():
        typed_col = f'{col_name}{SEP}{suffix}'
        if typed_col in table_columns:
            values[typed_col] = coerce_fn(raw_value)


def _get_index_ref(case, identifier):
    """Return the referenced_id for a case index, or None."""
    for index in case.live_indices:
        if index.identifier == identifier:
            return index.referenced_id
    return None
