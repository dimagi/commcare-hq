import simplejson
from corehq.apps.api.es import CaseES
from corehq.elastic import get_es
from dimagi.utils.logging import notify_exception


class CasePaginator():
    def __init__(self, domain, params, case_type=None, owner_ids=None,
                 user_ids=None, status=None, sort_block=None,
                 filter=None, search_string=None):
        self.domain = domain.lower()
        self.params = params
        self.case_type = case_type.lower()
        self.owner_ids = owner_ids
        self.user_ids = user_ids
        self.status = status or None
        self.sort_block = sort_block or {"modified_on": {"order": "desc"}}
        self.filter = filter
        self.case_es = CaseES(self.domain)
        self.search_string = search_string

        assert self.status in ('open', 'closed', None)

    def results(self):
        """Elasticsearch Results"""

        # there's no point doing filters that are like owner_id:(x1 OR x2 OR ... OR x612)
        # so past a certain number just exclude
        MAX_IDS = 50

        def _filter_gen(key, list):
            if list and len(list) < MAX_IDS:
                yield {"terms": {
                    key: [item.lower() if item else "" for item in list]
                }}

            # demo user hack
            elif list and "demo_user" not in list:
                yield {"not": {"term": {key: "demo_user"}}}

        def _domain_term():
            return {"term": {"domain.exact": self.domain}}

        if self.params.search:
            #these are not supported/implemented on the UI side, so ignoring (dmyung)
            pass

        subterms = [_domain_term(), self.filter] if self.filter else [_domain_term()]
        if self.case_type:
            subterms.append({"term": {"type": self.case_type}})

        if self.status:
            subterms.append({"term": {"closed": (self.status == 'closed')}})

        user_filters = list(_filter_gen('owner_id', self.owner_ids)) + \
                       list(_filter_gen('user_id', self.owner_ids))
        if user_filters:
            subterms.append({'or': user_filters})

        if self.search_string:
            query_block = {"query_string": {"query": self.query_string}} #todo, make sure this doesn't suck
        else:
            query_block = {"match_all": {}}

        and_block = {'and': subterms} if subterms else {}

        es_query = {
            'query': {
                'filtered': {
                    'query': query_block,
                    'filter': and_block
                }
            },
            'sort': self.sort_block,
            'from': self.params.start,
            'size': self.params.count,
        }

        print simplejson.dumps(es_query, indent=4)
        es_results = self.case_es.run_query(es_query)
        if es_results.has_key('error'):
            notify_exception(None, "Error in case list elasticsearch query: %s" % es_results['error'])
            return {
                'skip': self.params.start,
                'limit': self.params.count,
                'rows': [],
                'total_rows': 0
            }

        #transform the return value to something compatible with the report listing
        ret = {
            'skip': self.params.start,
            'limit': self.params.count,
            'rows': [{'doc': x['_source']} for x in es_results['hits']['hits']],
            'total_rows': es_results['hits']['total']
        }
        return ret
