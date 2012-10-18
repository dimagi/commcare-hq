from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators import inline
from django.conf import settings
import rawes

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
        """Lucene Results"""

        # there's no point doing filters that are like owner_id:(x1 OR x2 OR ... OR x612)
        # so past a certain number just exclude
        MAX_IDS = 50

        def join_None(string):
            def _inner(things):
                return string.join([thing or '""' for thing in things])

            return _inner

        query_prototype = """{
"query": {
"filtered" : {
"query" : {
"term" : { "case.domain" : "localdmyung" }
},

"filter" : {
"and" : [
    {
    "or" : {
    "filters" : [
        {
        "term" : { "case.owner_id" : "9d207c07d68d5da97290e38905c9adac" }
        },
        {
        "term" : { "case.owner_id" : "eadf13bfc89b0fd9b151566ee537ded1" }
        },
        {
        "term" : { "case.owner_id" : "" }
        }
    ]
    }
    },
    {
    "or" : {
    "filters" : [
        {
        "term" : { "case.user_id" : "9d207c07d68d5da97290e38905c9adac" }
        },
        {
        "term" : { "case.user_id" : "eadf13bfc89b0fd9b151566ee537ded1" }
        },
        {
        "term" : { "case.user_id" : "" }
        }
    ]
    }
    }
]
}
}
}
}
"""
        es = rawes.Elastic('%s:%s' % (settings.ELASTICSEARCH_HOST, settings.ELASTICSEARCH_PORT))

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

        def owner_filters():
            yield list(_filter_gen('case.owner_id', self.owner_ids))

        def user_filters():
            yield list(_filter_gen('case.user_id', self.owner_ids))

        if self.params.search:
            #these are not supported/implemented on the UI side, so ignoring (dmyung)
            pass

        es_query = {}
        es_query['query'] = {}
        es_query['query']['filtered'] = {}
        es_query['query']['filtered']['query'] = {}
        es_query['query']['filtered']['query']['term'] = {'case.domain': self.domain}
        es_query['query']['filtered']['filter'] = {}
        es_query['query']['filtered']['filter']['and'] = []

#        if self.case_type:
#            es_query['filtered']['filter']['and'].append({"term": {"case.type": self.case_type}})

        if self.status:
            if self.status == 'closed':
                is_closed = True
            else:
                is_closed = False
            es_query['query']['filtered']['filter']['and'].append({"term": {"case.closed": is_closed}})

        ofilters = list(owner_filters())
        if len(ofilters) > 0:
            owner_filter_block = {}
            owner_filter_block['or'] = {}
            owner_filter_block['or']['filters'] = ofilters
            es_query['query']['filtered']['filter']['and'].append(owner_filter_block)

        ufilters = list(user_filters())
        if len(ufilters) > 0:
            user_filter_block = {}
            user_filter_block['or'] = {}
            user_filter_block['or']['filters'] = ufilters
            es_query['query']['filtered']['filter']['and'].append(user_filter_block)

        es_query['sort'] = [
            {"case.modified_on": {"order": "asc"}},
        ]
        es_query['from'] = self.params.start
        es_query['size'] = self.params.count


        import simplejson
        print  simplejson.dumps(es_query)

        results = es.get('hqcases/case/_search', data=es_query)
        #print results
        ret = {}
        ret['skip'] = self.params.start
        ret['limit'] = self.params.count
        ret['rows'] = []
        ret['total_rows'] = results['hits']['total']
        for res in results['hits']['hits']:
            ret['rows'].append({'doc': res['_source']})
        return ret