def get_open_case_ids(owner_id):
    """
    Get all open case ids for a given owner
    """
    return _get_case_ids(owner_id, False)


def get_closed_case_ids(owner_id):
    """
    Get all closed case ids for a given owner
    """
    return _get_case_ids(owner_id, True)


def _get_case_ids(owner_id, is_closed):
    from casexml.apps.case.models import CommCareCase
    return [row['id'] for row in CommCareCase.get_db().view(
        'case/by_owner',
        reduce=False,
        key=[owner_id, is_closed],
    )]
