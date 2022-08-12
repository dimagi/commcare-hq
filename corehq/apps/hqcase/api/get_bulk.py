from corehq.apps.es.case_search import ElasticCaseSearch
from corehq.apps.hqcase.api.core import serialize_es_case


def get_bulk(domain, case_ids):
    results = ElasticCaseSearch().get_docs(case_ids)
    return {
        'matching_records': len(results),
        'cases': [serialize_es_case(case) for case in results]
    }
