from sqlalchemy.dialects.postgresql import insert

from corehq.apps.project_db.coerce import coerce_to_date, coerce_to_number

FIXED_COLUMNS = {
    'case_id', 'owner_id', 'case_name', 'opened_on', 'closed_on',
    'modified_on', 'closed', 'external_id', 'server_modified_on',
}


def upsert_case(engine, table, case_data):
    """Insert or update a single case row in a project DB table.

    ``case_data`` is a dict with:
    - Fixed field keys (``case_id``, ``owner_id``, etc.) passed through directly
    - Case property keys (without ``prop_`` prefix) mapped to ``prop_<key>`` columns
    - An ``indices`` key mapping identifiers to referenced case IDs

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


def _build_values_dict(case_data, table_columns):
    """Map case_data keys to table column names, skipping unknown columns."""
    values = {}
    for key, value in case_data.items():
        if key == 'indices':
            for identifier, referenced_id in value.items():
                col_name = f'idx_{identifier}'
                if col_name in table_columns:
                    values[col_name] = referenced_id
        elif key in FIXED_COLUMNS:
            values[key] = value
        else:
            col_name = f'prop_{key}'
            if col_name in table_columns:
                values[col_name] = value
                _set_typed_columns(values, col_name, value, table_columns)
    return values


# Maps typed column suffixes to their coercion functions.
_TYPED_COERCIONS = {
    '_date': coerce_to_date,
    '_numeric': coerce_to_number,
}


def _set_typed_columns(values, col_name, raw_value, table_columns):
    """If typed companion columns exist, coerce and set their values."""
    for suffix, coerce_fn in _TYPED_COERCIONS.items():
        typed_col = f'{col_name}{suffix}'
        if typed_col in table_columns:
            values[typed_col] = coerce_fn(raw_value)
