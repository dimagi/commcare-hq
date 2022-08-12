import dataclasses
from dataclasses import dataclass, field
from operator import itemgetter

from corehq.apps.es.case_search import ElasticCaseSearch
from corehq.apps.hqcase.api.core import serialize_es_case, UserError
from corehq.apps.hqcase.api.get_list import MAX_PAGE_SIZE
from corehq.form_processor.models.util import sort_with_id_list


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

    If the case is not found or belongs to a different domain then
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
    results = ElasticCaseSearch().get_docs(case_ids)

    def _serialize_doc(doc):
        found_ids.add(doc['_id'])

        if doc['domain'] == domain:
            return serialize_es_case(doc)

        error_ids.add(doc['_id'])
        return _get_error_doc(doc['_id'])

    error_ids = set()
    found_ids = set()

    final_results = [_serialize_doc(doc) for doc in results]

    missing_ids = set(case_ids) - found_ids
    final_results.extend([
        _get_error_doc(missing_id) for missing_id in missing_ids
    ])

    sort_with_id_list(final_results, case_ids, 'case_id', operator=itemgetter)

    total = len(case_ids)
    not_found = len(error_ids) + len(missing_ids)
    return BulkFetchResults(final_results, total - not_found, not_found)


def _get_cases_by_external_id(domain, external_ids):
    return BulkFetchResults()


def _get_error_doc(case_id):
    return {'case_id': case_id, 'error': 'not found'}
