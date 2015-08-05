from collections import namedtuple
from casexml.apps.case.sharedmodels import CommCareCaseIndex


def get_indexed_case_ids(domain, case_ids):
    """
    Given a base list of case ids, gets all ids of cases they reference (parent cases)
    """
    from casexml.apps.case.models import CommCareCase
    keys = [[domain, case_id, 'index'] for case_id in case_ids]
    return [r['value']['referenced_id'] for r in CommCareCase.get_db().view(
        'case/related',
        keys=keys,
        reduce=False,
    )]


def get_reverse_indexed_case_ids(domain, case_ids):
    """
    Given a base list of case ids, gets all ids of cases that reference them (child cases)
    """
    return [r.case_id for r in get_all_reverse_indices_info(domain, case_ids)]


def get_reverse_indexed_cases(domain, case_ids):
    """
    Given a base list of cases, gets all wrapped cases that directly
    reference them (child cases).
    """
    from casexml.apps.case.models import CommCareCase
    keys = [[domain, case_id, 'reverse_index'] for case_id in case_ids]
    return CommCareCase.view(
        'case/related',
        keys=keys,
        reduce=False,
        include_docs=True,
    )


IndexInfo = namedtuple('IndexInfo', ['case_id', 'identifier', 'referenced_id', 'referenced_type'])


def get_all_reverse_indices_info(domain, case_ids):
    from casexml.apps.case.models import CommCareCase
    keys = [[domain, case_id, 'reverse_index'] for case_id in case_ids]

    def _row_to_index_info(row):
        return IndexInfo(
            case_id=row['id'],
            identifier=row['value']['identifier'],
            referenced_id=row['key'][1],
            referenced_type=row['value']['referenced_type'],
        )
    return map(_row_to_index_info, CommCareCase.get_db().view(
        'case/related',
        keys=keys,
        reduce=False,
    ))


def get_reverse_indices_json(case):
    from casexml.apps.case.models import CommCareCase
    return CommCareCase.get_db().view(
        "case/related",
        key=[case['domain'], case['_id'], "reverse_index"],
        reduce=False,
        wrapper=lambda r: r['value']
    ).all()


def get_reverse_indices(case):
    return [CommCareCaseIndex.wrap(raw)
            for raw in get_reverse_indices_json(case)]
