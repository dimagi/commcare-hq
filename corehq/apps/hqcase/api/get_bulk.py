import dataclasses
from collections import Counter
from dataclasses import dataclass, field

from corehq.apps.es.case_search import ElasticCaseSearch, CaseSearchES
from corehq.apps.hqcase.api.core import serialize_es_case, UserError
from corehq.apps.hqcase.api.get_list import MAX_PAGE_SIZE


@dataclass
class BulkFetchResults:
    cases: list = field(default_factory=list)
    matching_records: int = 0
    missing_records: int = 0

    def merge(self, results):
        self.cases.extend(results.cases)
        self.matching_records += results.matching_records
        self.missing_records += results.missing_records


def get_bulk(domain, case_ids=None, external_ids=None):
    """Get cases in bulk.

    This must return a result for each case ID passed in and the results must
    be in the same order as the original list of case IDs.

    If both case IDs and external IDs are passed then results will include
    cases loaded by ID first followed by cases loaded by external ID.

    If a case is not found or belongs to a different domain then
    an error stub is included in the result set.
    """
    case_ids = case_ids or []
    external_ids = external_ids or []
    if len(case_ids) + len(external_ids) > MAX_PAGE_SIZE:
        raise UserError(f"You cannot request more than {MAX_PAGE_SIZE} cases per request.")

    results = BulkFetchResults()
    if case_ids:
        results.merge(_get_cases_by_id(domain, case_ids))

    if external_ids:
        results.merge(_get_cases_by_external_id(domain, external_ids))

    return dataclasses.asdict(results)


def _get_cases_by_id(domain, case_ids):
    es_results = ElasticCaseSearch().get_docs(case_ids)
    return _prepare_result(
        domain, es_results, case_ids,
        es_id_field='_id', serialized_id_field='case_id'
    )


def _get_cases_by_external_id(domain, external_ids):
    query = CaseSearchES().domain(domain).external_id(external_ids)
    es_results = query.run().hits

    return _prepare_result(
        domain, es_results, external_ids,
        es_id_field='external_id', serialized_id_field='external_id'
    )


def _prepare_result(domain, es_results, doc_ids, es_id_field, serialized_id_field):

    def _get_error_doc(id_value):
        return {serialized_id_field: id_value, 'error': 'not found'}

    def _serialize_doc(doc):
        found_ids.add(doc[es_id_field])

        if doc['domain'] == domain:
            return serialize_es_case(doc)

        error_ids.add(doc[es_id_field])
        return _get_error_doc(doc[es_id_field])

    error_ids = set()
    found_ids = set()

    serialized_results = [_serialize_doc(doc) for doc in es_results]

    missing_ids = set(doc_ids) - found_ids
    serialized_results.extend([
        _get_error_doc(missing_id) for missing_id in missing_ids
    ])

    # This orders the results in the same order as the input IDs. It also has the effect
    # of including duplicate results for duplicate IDs
    results_by_id = {res[serialized_id_field]: res for res in serialized_results}
    ordered_results = [
        results_by_id[doc_id] for doc_id in doc_ids
    ]

    # if there are duplicate IDs that were not found our doc counts are going to be off
    missing_duplicate_count = sum(
        count - 1  # we already have 1 in the 'missing_ids' so decrease the count by 1
        for id_, count in Counter(doc_ids).items()
        if count > 1 and id_ not in found_ids
    )

    total = len(doc_ids)
    not_found = len(error_ids) + len(missing_ids) + missing_duplicate_count
    return BulkFetchResults(ordered_results, total - not_found, not_found)
