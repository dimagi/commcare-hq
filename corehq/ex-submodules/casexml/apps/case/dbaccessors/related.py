from casexml.apps.case.sharedmodels import CommCareCaseIndex
from casexml.apps.case.const import CASE_INDEX_CHILD, CASE_INDEX_EXTENSION
from corehq.form_processor.interfaces.dbaccessors import CaseIndexInfo


def get_reverse_indexed_case_ids(domain, case_ids):
    """
    Given a base list of case ids, gets all ids of cases that reference them (child cases)
    """
    return [r.case_id for r in get_all_reverse_indices_info(domain, case_ids, CASE_INDEX_CHILD)]


def get_all_reverse_indices_info(domain, case_ids, relationship=None, exclude_for_case_type=None):
    from casexml.apps.case.models import CommCareCase

    def _row_to_index_info(row):
        return CaseIndexInfo(
            case_id=row['id'],
            identifier=row['value']['identifier'],
            referenced_id=row['key'][1],
            referenced_type=row['value']['referenced_type'],
            relationship=row['value']['relationship']
        )

    return [
        _row_to_index_info(row)
        for row in CommCareCase.get_db().view(
            'case_indices/related',
            keys=_get_keys_for_reverse_index_view(domain, case_ids, relationship),
            reduce=False,
        )
        if not exclude_for_case_type or row['value']['referenced_type'] != exclude_for_case_type
    ]


def _get_keys_for_reverse_index_view(domain, case_ids, relationship=None):
    assert not isinstance(case_ids, (str, bytes))
    if relationship is None:
        return [[domain, case_id, 'reverse_index', reln]
                for case_id in case_ids for reln in [CASE_INDEX_CHILD, CASE_INDEX_EXTENSION]]
    else:
        return [[domain, case_id, 'reverse_index', relationship] for case_id in case_ids]


def get_reverse_indices_json(domain, case_id):
    from casexml.apps.case.models import CommCareCase
    return CommCareCase.get_db().view(
        "case_indices/related",
        startkey=[domain, case_id, "reverse_index"],
        endkey=[domain, case_id, "reverse_index", {}],
        reduce=False,
        wrapper=lambda r: r['value'],
    ).all()


def get_reverse_indices(case):
    return get_reverse_indices_for_case_id(case['domain'], case['_id'])


def get_reverse_indices_for_case_id(domain, case_id):
    return [CommCareCaseIndex.wrap(raw)
            for raw in get_reverse_indices_json(domain, case_id)]
