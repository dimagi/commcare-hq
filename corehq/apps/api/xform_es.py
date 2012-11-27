import logging
from dimagi.utils.decorators import inline
from corehq.elastic import get_es

class XFormES():
    def __init__(self, domain, params, xmlns=None, owner_ids=None, user_ids=None):
        self.domain = domain
        self.params = params
        self.xmlns = xmlns
        self.owner_ids = owner_ids
        self.user_ids = user_ids

    def results(self):
        """Elasticsearch XForm Results"""
        MAX_IDS = 50

        def join_None(string):
            def _inner(things):
                return string.join([thing or '""' for thing in things])

            return _inner

        def _filter_gen(key, list):
            if list and len(list) < MAX_IDS:
                for item in list:
                    if item is not None:
                        yield {"term": {key: item}}
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
            if self.xmlns:
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
            logging.exception("Error in case list elasticsearch query: %s" % es_results['error'])
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