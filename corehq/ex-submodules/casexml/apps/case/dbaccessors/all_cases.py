from dimagi.utils.couch.database import iter_docs


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


def get_open_case_ids_in_domain(domain, type=None, owner_id=None):
    from casexml.apps.case.models import CommCareCase
    if owner_id is not None and type is None:
        key = ["open owner", domain, owner_id]
    else:
        key = ["open type owner", domain]
        if type is not None:
            key += [type]
        if owner_id is not None:
            key += [owner_id]

    case_ids = [row['id'] for row in CommCareCase.get_db().view(
        'case/all_cases',
        startkey=key,
        endkey=key + [{}],
        reduce=False,
        include_docs=False
    )]
    return case_ids


def get_open_case_docs_in_domain(domain, type=None, owner_id=None):
    from casexml.apps.case.models import CommCareCase
    case_ids = get_open_case_ids_in_domain(domain, type, owner_id)
    for doc in iter_docs(CommCareCase.get_db(), case_ids):
        yield doc
