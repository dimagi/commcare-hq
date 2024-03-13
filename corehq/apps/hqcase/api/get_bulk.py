import dataclasses
from dataclasses import dataclass, field

from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.hqcase.api.core import UserError, serialize_es_case
from corehq.apps.hqcase.api.get_list import MAX_PAGE_SIZE
from corehq.apps.reports.standard.cases.utils import query_location_restricted_cases


@dataclass
class BulkFetchResults:
    cases: list = field(default_factory=list)
    matching_records: int = 0
    missing_records: int = 0

    def merge(self, results):
        self.cases.extend(results.cases)
        self.matching_records += results.matching_records
        self.missing_records += results.missing_records


def get_bulk(domain, couch_user, case_ids=None, external_ids=None):
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
        results.merge(_get_cases_by_id(domain, case_ids, couch_user))

    if external_ids:
        results.merge(_get_cases_by_external_id(domain, external_ids, couch_user))

    return dataclasses.asdict(results)


def _get_cases_by_id(domain, case_ids, couch_user):
    query = CaseSearchES().domain(domain).case_ids(case_ids)
    return _get_cases(
        domain,
        case_ids,
        couch_user,
        query,
        es_id_field='_id',
        serialized_id_field='case_id'
    )


def _get_cases_by_external_id(domain, external_ids, couch_user):
    query = CaseSearchES().domain(domain).external_id(external_ids)
    return _get_cases(
        domain,
        external_ids,
        couch_user,
        query,
        es_id_field='external_id',
        serialized_id_field='external_id'
    )


def _get_cases(domain, id_list, couch_user, query, es_id_field, serialized_id_field):
    if not couch_user.has_permission(domain, 'access_all_locations'):
        query = query_location_restricted_cases(query, domain, couch_user)

    es_results = query.run().hits
    return _prepare_result(
        domain, es_results, id_list,
        es_id_field=es_id_field, serialized_id_field=serialized_id_field
    )


def _prepare_result(domain, es_results, doc_ids, es_id_field, serialized_id_field):

    def _get_error_doc(id_value):
        return {serialized_id_field: id_value, 'error': 'not found'}

    def _get_doc(doc_id):
        doc = results_by_id.get(doc_id)
        if doc:
            return serialize_es_case(doc)

        missing_ids.append(doc_id)
        return _get_error_doc(doc_id)

    missing_ids = []
    results_by_id = {
        res[es_id_field]: res for res in es_results
        if res['domain'] == domain
    }
    final_results = [_get_doc(doc_id) for doc_id in doc_ids]

    total = len(doc_ids)
    not_found = len(missing_ids)
    return BulkFetchResults(final_results, total - not_found, not_found)
