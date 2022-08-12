from corehq.apps.es.case_search import ElasticCaseSearch
from corehq.apps.hqcase.api.core import serialize_es_case


def get_bulk(domain, case_ids):
    results = ElasticCaseSearch().get_docs(case_ids)
    missing_count = 0
    final_results = []
    found_ids = set()
    for doc in results:
        found_ids.add(doc['_id'])
        if doc['domain'] != domain:
            final_results.append(_get_error_doc(doc['_id']))
            missing_count += 1
        else:
            final_results.append(serialize_es_case(doc))

    missing_ids = set(case_ids) - found_ids
    missing_count += len(missing_ids)
    for missing_id in missing_ids:
        final_results.append(_get_error_doc(missing_id))

    return {
        'matching_records': len(final_results) - missing_count,
        'missing_records': missing_count,
        'cases': final_results
    }


def _get_error_doc(case_id):
    return {'case_id': case_id, 'error': 'not found'}
