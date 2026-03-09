_FIXED_FIELD_NAMES = {
    'case_id', 'owner_id', 'case_name', 'opened_on', 'closed_on',
    'modified_on', 'closed', 'external_id', 'server_modified_on',
}

# Keys in case_json that must never overwrite fixed fields or the
# 'indices' key assembled from live_indices.
_RESERVED_KEYS = _FIXED_FIELD_NAMES | {'indices'}


def case_to_row_dict(case):
    """Convert a CommCareCase instance to a dict suitable for ``upsert_case``.

    Extracts fixed fields, dynamic properties from ``case_json``, and
    index references from ``live_indices``.
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
    }
    for key, value in case.case_json.items():
        if key not in _RESERVED_KEYS:
            row[key] = value
    row['indices'] = {
        index.identifier: index.referenced_id
        for index in case.live_indices
    }
    return row
