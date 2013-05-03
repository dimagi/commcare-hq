
from corehq.apps.api.es import FullCaseES

def due_list_by_task_name(target_date, owner_id=None, case_es=None, size=0, case_type='task'):
    """
    Returns the due list in a dictionary of the form {type: count}
    """
     
    case_es = case_es or FullCaseES(BIHAR_DOMAIN)
    es_type = 'fullcase_%(domain)s__%(case_type)s' % { 'domain': 'bihar', 'case_type': 'task' }
    facet_name = 'vaccination_names'    

    # The type of vaccination is stored in the `name` field in ElasticSearch
    # so we can get the sums directly as facets on `name.exact` where the `.exact`
    # is to avoid tokenization so that "OPV 1" does not create two facets.

    base_query = case_es.base_query(start=0, size=size)

    owner_filter = {"match_all":{}} if owner_id is None else {"term": {"owner_id": owner_id}}

    filter = {
        "and": [
            owner_filter,
            {"term": {"closed": False}},
            {"term": {"type": case_type}},
            {"range": {"date_eligible": {"to": target_date.isoformat() }}},
            {"range": {"date_expires": {"from": target_date.isoformat()}}},
        ]
    }

    base_query['filter']['and'] += filter['and']
    base_query['facets'] = {
        facet_name: {
            "terms": {"field":"name.exact"},
            "facet_filter": filter # This controls the records processed for the summation
        }
    }

    es_result = case_es.run_query(base_query, es_type=es_type)

    return dict([ (facet['term'], facet['count']) for facet in es_result['facets'][facet_name]['terms'] ])
    
        
