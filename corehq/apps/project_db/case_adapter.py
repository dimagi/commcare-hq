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
    row.update(case.case_json)
    row['indices'] = {
        index.identifier: index.referenced_id
        for index in case.live_indices
    }
    return row
