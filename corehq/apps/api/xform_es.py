import logging
import pdb
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
import simplejson
from corehq.apps.domain.decorators import login_and_domain_required
from dimagi.utils.decorators import inline
from corehq.elastic import get_es
from django.views.generic import View


class ESView(View):

    #note - for security purposes, csrf protection is ENABLED
    #search POST queries must take the following format:
    #query={query_json}
    #csrfmiddlewaretoken=token

    #in curl, this is:
    #curl -b "csrftoken=<csrftoken>;sessionid=<session_id>" -H "Content-Type: application/json" -XPOST http://server/a/domain/api/v0.1/xform_es/
    #     -d"query=@myquery.json&csrfmiddlewaretoken=<csrftoken>"

    http_method_names = ['get', 'post', 'head', ]
    def get(self, *args, **kwargs):
        raise NotImplementedError("Not implemented")
    def post(self,  *args, **kwargs):
        raise NotImplementedError("Not implemented")
    def head(self, *args, **kwargs):
        raise NotImplementedError("Not implemented")
    @method_decorator(login_and_domain_required)
    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        req = args[0]
        self.pretty = req.GET.get('pretty', False)
        if self.pretty:
            self.indent=4
        else:
            self.indent=None
        ret =  super(ESView, self).dispatch(*args, **kwargs)
        return ret


class XFormES(ESView):
#    def __init__(self, domain, params, xmlns=None, owner_ids=None, user_ids=None):
#        self.domain = domain
#        self.params = params
#        self.xmlns = xmlns
#        self.owner_ids = owner_ids
#        self.user_ids = user_ids

    def __init__(self, *args, **kwargs):
        self.es = get_es()

    def base_query(self, domain, start=0, size=10):
        query = {
            "filter": {
                "and": [
                    {
                        "term": {
                            "domain.exact": domain
                        }
                    }
                ]
            },
            "sort": {
                "received_on": "desc"
            },
            "size": size,
            "from":start
        }
        return query

    def run_query(self, es_query):
        print simplejson.dumps(es_query, indent=4)
        es_results = self.es.get('xforms/_search', data=es_query)

        if es_results.has_key('error'):
            logging.exception("Error in xform elasticsearch query: %s" % es_results['error'])
            return {'Error': "No data"}
#        print "total results: %d" % es_results['hits']['total']
        return es_results

    def get(self, *args, **kwargs):
        """
        Very basic querying based upon GET parameters.
        """
        size = self.request.GET.get('size', 10)
        start = self.request.GET.get('start', 0)
        domain = self.request.domain
        query_results = self.run_query(self.base_query(domain, start=start, size=size))
        query_output = simplejson.dumps(query_results, indent=self.indent)
        response = HttpResponse(query_output, content_type="application/json")
        return response

    def post(self, *args, **kwargs):
        """
        More powerful querying using POST params.
        """
        try:
            raw_post = self.request.raw_post_data
            raw_query = simplejson.loads(raw_post)
        except Exception, ex:
            content_response = dict(message="Error parsing query request", exception=ex.message)
            response = HttpResponse(status=406, content=simplejson.dumps(content_response))
            return response

        domain = self.request.domain
        query_results = self.run_query(raw_query)
        query_output = simplejson.dumps(query_results, indent=self.indent)
        response = HttpResponse(query_output, content_type="application/json")
        return response

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