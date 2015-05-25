

def get_total_case_count():
    """
    Total count of all cases in the database.
    """
    from casexml.apps.case.models import CommCareCase
    results = CommCareCase.get_db().view(
        'case/by_owner',
        reduce=True,
    ).one()
    return results['value'] if results else 0


def get_all_case_ids(owner_id):
    return _get_case_ids(owner_id, is_closed=None)


def get_open_case_ids(owner_id):
    """
    Get all open case ids for a given owner
    """
    return _get_case_ids(owner_id, is_closed=False)


def get_closed_case_ids(owner_id):
    """
    Get all closed case ids for a given owner
    """
    return _get_case_ids(owner_id, is_closed=True)


def _get_case_ids(owner_id, is_closed):
    from casexml.apps.case.models import CommCareCase
    if is_closed is None:
        key = [owner_id]
    else:
        key = [owner_id, is_closed]

    return [row['id'] for row in CommCareCase.get_db().view(
        'case/by_owner',
        reduce=False,
        key=key,
    )]
