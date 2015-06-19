import itertools
import logging
from casexml.apps.case.dbaccessors import get_reverse_indices_json
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xform import CaseDbCache


def get_related_cases(initial_cases, domain, strip_history=False, search_up=True):
    """
    Gets the flat list of related cases based on a starting list.
    Walks all the referenced indexes recursively.
    If search_up is True, all cases and their parent cases are returned.
    If search_up is False, all cases and their child cases are returned.
    """
    if not initial_cases:
        return {}

    # infer whether to wrap or not based on whether the initial list is wrapped or not
    # initial_cases may be a list or a set
    wrap = isinstance(next(iter(initial_cases)), CommCareCase)

    # todo: should assert that domain exists here but this breaks tests
    case_db = CaseDbCache(domain=domain,
                          strip_history=strip_history,
                          deleted_ok=True,
                          wrap=wrap,
                          initial=initial_cases)

    def indices(case):
        return case['indices'] if search_up else get_reverse_indices_json(case)

    relevant_cases = {}
    relevant_deleted_case_ids = []

    cases_to_process = list(case for case in initial_cases)
    directly_referenced_indices = itertools.chain(
        *[[index['referenced_id'] for index in indices(case)]
          for case in initial_cases]
    )
    case_db.populate(directly_referenced_indices)

    def process_cases(cases):
        new_relations = set()
        for case in cases:
            if case and case['_id'] not in relevant_cases:
                relevant_cases[case['_id']] = case
                if case['doc_type'] == 'CommCareCase-Deleted':
                    relevant_deleted_case_ids.append(case['_id'])
                new_relations.update(index['referenced_id'] for index in indices(case))

        if new_relations:
            case_db.populate(new_relations)
            return [case_db.get(related_case) for related_case in new_relations]

    while cases_to_process:
        cases_to_process = process_cases(cases_to_process)

    if relevant_deleted_case_ids:
        logging.info('deleted cases included in footprint (restore): %s' % (
            ', '.join(relevant_deleted_case_ids)
        ))

    return relevant_cases


def get_footprint(initial_case_list, domain, strip_history=False):
    return get_related_cases(initial_case_list, domain, strip_history=strip_history, search_up=True)
