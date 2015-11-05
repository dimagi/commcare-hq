from collections import namedtuple
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from casexml.apps.case.const import CASE_INDEX_CHILD, CASE_INDEX_EXTENSION


def get_indexed_case_ids(domain, case_ids):
    """
    Given a base list of case ids, gets all ids of cases they reference (parent and host cases)
    """
    from casexml.apps.case.models import CommCareCase
    keys = [[domain, case_id, 'index'] for case_id in case_ids]
    return [r['value']['referenced_id'] for r in CommCareCase.get_db().view(
        'case/related',
        keys=keys,
        reduce=False,
    )]


def get_extension_case_ids(domain, case_ids):
    """
    Given a base list of case ids, for those that are open, get all ids of all extension cases that reference them
    """
    return [r.case_id for r in get_all_reverse_indices_info(domain, case_ids, CASE_INDEX_EXTENSION)]


def get_reverse_indexed_case_ids(domain, case_ids):
    """
    Given a base list of case ids, gets all ids of cases that reference them (child cases)
    """
    return [r.case_id for r in get_all_reverse_indices_info(domain, case_ids, CASE_INDEX_CHILD)]


def get_reverse_indexed_cases(domain, case_ids, relationship=CASE_INDEX_CHILD):
    """
    Given a base list of cases, gets all wrapped cases that directly
    reference them (with relationship <relationship>).
    """
    from casexml.apps.case.models import CommCareCase
    keys = [[domain, case_id, 'reverse_index', relationship] for case_id in case_ids]
    return CommCareCase.view(
        'case/related',
        keys=keys,
        reduce=False,
        include_docs=True,
    )


IndexInfo = namedtuple('IndexInfo', ['case_id', 'identifier', 'referenced_id', 'referenced_type', 'relationship'])


def get_all_reverse_indices_info(domain, case_ids, relationship=None):
    from casexml.apps.case.models import CommCareCase
    if relationship is None:
        keys = [[domain, case_id, 'reverse_index', reln]
                for case_id in case_ids for reln in [CASE_INDEX_CHILD, CASE_INDEX_EXTENSION]]
    else:
        keys = [[domain, case_id, 'reverse_index', relationship] for case_id in case_ids]

    def _row_to_index_info(row):
        return IndexInfo(
            case_id=row['id'],
            identifier=row['value']['identifier'],
            referenced_id=row['key'][1],
            referenced_type=row['value']['referenced_type'],
            relationship=row['value']['relationship']
        )
    return map(_row_to_index_info, CommCareCase.get_db().view(
        'case/related',
        keys=keys,
        reduce=False,
    ))


def get_reverse_indices_json(domain, case_id, relationship=CASE_INDEX_CHILD):
    from casexml.apps.case.models import CommCareCase
    return CommCareCase.get_db().view(
        "case/related",
        key=[domain, case_id, "reverse_index", relationship],
        reduce=False,
        wrapper=lambda r: r['value']
    ).all()


def get_reverse_indices(case):
    return get_reverse_indices_for_case_id(case['domain'], case['_id'])


def get_reverse_indices_for_case_id(domain, case_id):
    return [CommCareCaseIndex.wrap(raw)
            for raw in get_reverse_indices_json(domain, case_id)]
