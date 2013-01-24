from corehq.elastic import get_es
from dimagi.utils.logging import notify_exception


class CasePaginator():
    def __init__(self, domain, params, case_type=None, owner_ids=None,
                 user_ids=None, status=None, sort_key=None, sort_order=None,
                 filter=None):
        self.domain = domain
        self.params = params
        self.case_type = case_type
        self.owner_ids = owner_ids
        self.user_ids = user_ids
        self.status = status or None
        self.sort_key = sort_key or 'modified_on'
        self.sort_order = sort_order or 'desc'
        self.filter = filter

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

        if self.params.search:
            #these are not supported/implemented on the UI side, so ignoring (dmyung)
            pass

        subterms = [self.filter] if self.filter else []
        if self.case_type:
            subterms.append({"term": {"type": self.case_type}})

        if self.status:
            subterms.append({"term": {"closed": (self.status == 'closed')}})

        user_filters = list(_filter_gen('owner_id', self.owner_ids)) + \
                       list(_filter_gen('user_id', self.owner_ids))
        if user_filters:
            subterms.append({'or': user_filters})

        and_block = {'and': subterms} if subterms else {}

        es_query = {
            'query': {
                'filtered': {
                    'query': {
                        'match': {'domain.exact': self.domain}
                    },
                    'filter': and_block
                }
            },
            'sort': {
                self.sort_key: {'order': self.sort_order}
            },
            'from': self.params.start,
            'size': self.params.count,
        }
        es_results = get_es().get('hqcases/_search', data=es_query)

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
