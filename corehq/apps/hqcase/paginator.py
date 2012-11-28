import logging
from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators import inline
from django.conf import settings
import rawes
from corehq.elastic import get_es
from dimagi.utils.logging import notify_exception

class CasePaginator():
    def __init__(self, domain, params, case_type=None, owner_ids=None, user_ids=None, status=None):
        self.domain = domain
        self.params = params
        self.case_type = case_type
        self.owner_ids = owner_ids
        self.user_ids = user_ids
        self.status = status or None
        assert self.status in ('open', 'closed', None)

    def results(self):
        """Elasticsearch Results"""

        # there's no point doing filters that are like owner_id:(x1 OR x2 OR ... OR x612)
        # so past a certain number just exclude
        MAX_IDS = 50

        def join_None(string):
            def _inner(things):
                return string.join([thing or '""' for thing in things])

            return _inner

        def _filter_gen(key, list):
            if list and len(list) < MAX_IDS:
                for item in list:
                    if item is not None:
                        # elastic hates capital letters
                        yield {"term": {key: item.lower()}} 
                    else:
                        yield {"term" :{key: ""}}

            # demo user hack
            elif list and "demo_user" not in list:
                yield {"not": {"term": {key: "demo_user"}}}

        if self.params.search:
            #these are not supported/implemented on the UI side, so ignoring (dmyung)
            pass


        @inline
        def and_block():
            subterms = []
            if self.case_type:
                subterms.append({"term": {"type": self.case_type}})

            if self.status:
                if self.status == 'closed':
                    is_closed = True
                else:
                    is_closed = False
                subterms.append({"term": {"closed": is_closed}})

            userGroupFilters = []
            ofilters = list(_filter_gen('owner_id', self.owner_ids))
            if len(ofilters) > 0:
                userGroupFilters.append( {
                    'or': {
                        'filters': ofilters,
                    }
                })
            ufilters = list(_filter_gen('user_id', self.owner_ids))
            if len(ufilters) > 0:
                userGroupFilters.append( {
                    'or': {
                        'filters': ufilters,
                    }
                })
            if userGroupFilters:
                subterms.append({'or': userGroupFilters})
            if len(subterms) > 0:
                return {'and': subterms}
            else:
                return {}

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
                'modified_on': {'order': 'asc'}
            },
            'from': self.params.start,
            'size': self.params.count,
        }
        es_results = get_es().get('hqcases/_search', data=es_query)

        if es_results.has_key('error'):
            notify_exception("Error in case list elasticsearch query: %s" % es_results['error'])
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