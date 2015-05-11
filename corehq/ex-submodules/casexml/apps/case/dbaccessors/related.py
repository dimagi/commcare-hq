def get_indexed_case_ids(domain, case_ids):
    """
    Given a base list of case ids, gets all ids of cases they reference (parent cases)
    """
    return _get_related_case_ids(domain, case_ids, 'index')


def get_reverse_indexed_case_ids(domain, case_ids):
    """
    Given a base list of case ids, gets all ids of cases that reference them (child cases)
    """
    return _get_related_case_ids(domain, case_ids, 'reverse_index')


def _get_related_case_ids(domain, case_ids, reference_type):
    from casexml.apps.case.models import CommCareCase
    keys = [[domain, id, reference_type] for id in case_ids]
    return [row['value']['referenced_id'] for row in CommCareCase.get_db().view(
        'case/related',
        keys=keys,
        reduce=False,
    )]
