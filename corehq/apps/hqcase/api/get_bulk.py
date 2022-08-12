from corehq.apps.es.case_search import ElasticCaseSearch
from corehq.apps.hqcase.api.core import serialize_es_case


def get_bulk(domain, case_ids):
    results = ElasticCaseSearch().get_docs(case_ids)
    missing = 0
    final_results = []
    for doc in results:
        if doc['domain'] != domain:
            final_results.append(_get_error_doc(doc['_id']))
            missing += 1
        else:
            final_results.append(serialize_es_case(doc))

    return {
        'matching_records': len(final_results) - missing,
        'missing_records': missing,
        'cases': final_results
    }


def _get_error_doc(case_id):
    return {'case_id': case_id, 'error': 'not found'}
