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

    index = ""
    es = get_es()

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

    def run_query(self, es_query):
        """
        Run a more advanced POST based ES query

        Returns the raw query json back, or None if there's an error
        """
        #todo: backend audit logging of all these types of queries
        es_results = self.es[self.index].get('_search', data=es_query)
        if es_results.has_key('error'):
            logging.exception("Error in %s elasticsearch query: %s" % (self.index, es_results['error']))
            #return {'Error': "No data"}
            return None
        return es_results

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


class CaseES(ESView):
    index = "hqcases"


class XFormES(ESView):
    index = "xforms"
