from operator import itemgetter

from corehq.apps.es.case_search import ElasticCaseSearch
from corehq.apps.hqcase.api.core import serialize_es_case
from corehq.form_processor.models.util import sort_with_id_list


def get_bulk(domain, case_ids):
    """Get cases in bulk.

    This must return a result for each case ID passed in and the results must
    be in the same order as the original list of case IDs.

    If the case is not found or belongs to a different domain then
    an error stub is included in the result set.
    """
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
    return {
        'matching_records': total - not_found,
        'missing_records': not_found,
        'cases': final_results
    }


def _get_error_doc(case_id):
    return {'case_id': case_id, 'error': 'not found'}
