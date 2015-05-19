def get_all_case_owner_ids(domain):
    """
    Get all owner ids that are assigned to cases in a domain.
    """
    from casexml.apps.case.models import CommCareCase
    key = ["all owner", domain]
    submitted = CommCareCase.get_db().view(
        'case/all_cases',
        group_level=3,
        startkey=key,
        endkey=key + [{}],
    ).all()
    return set([row['key'][2] for row in submitted])
