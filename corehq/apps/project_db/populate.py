from sqlalchemy.dialects.postgresql import insert

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

    On conflict on ``case_id``, all non-PK columns are updated.
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
    return values
