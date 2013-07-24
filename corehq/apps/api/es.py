import logging
import simplejson
import six
import copy
from django.http import HttpResponse
from django.utils.decorators import method_decorator, classonlymethod
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.reports.filters.forms import FormsByApplicationFilter
from corehq.elastic import get_es
from django.views.generic import View
from dimagi.utils.logging import notify_exception


DEFAULT_SIZE = 10

class ESView(View):
    """
    Generic CBV for interfacing with the Elasticsearch REST api.
    This is necessary because tastypie's built in REST assumptions don't like
    ES's POST for querying, which we can set explicitly here.

    For security purposes, queries ought to be domain'ed by the requesting user, so a base_query
    is encouraged to be added.

    Access to the APIs can be done via url endpoints which are attached to the corehq.api.urls

    or programmatically via the self.run_query() method.

    This current iteration of the ESView must require a domain for its usage for security purposes.
    """
    #note - for security purposes, csrf protection is ENABLED
    #search POST queries must take the following format:
    #query={query_json}
    #csrfmiddlewaretoken=token

    #in curl, this is:
    #curl -b "csrftoken=<csrftoken>;sessionid=<session_id>" -H "Content-Type: application/json" -XPOST http://server/a/domain/api/v0.1/xform_es/
    #     -d"query=@myquery.json&csrfmiddlewaretoken=<csrftoken>"
    #or, call this programmatically to avoid CSRF issues.

    index = ""
    domain = ""
    es = None

    http_method_names = ['get', 'post', 'head', ]

    def __init__(self, domain):
        self.domain=domain.lower()
        self.es = get_es()

    def head(self, *args, **kwargs):
        raise NotImplementedError("Not implemented")

    @method_decorator(login_and_domain_required)
    #@method_decorator(csrf_protect)
    # todo: csrf_protect temporarily removed and left to implementor's prerogative
    # getting ajax'ed csrf token method needs revisit.
    def dispatch(self, *args, **kwargs):
        req = args[0]
        self.pretty = req.GET.get('pretty', False)
        if self.pretty:
            self.indent = 4
        else:
            self.indent = None
        ret = super(ESView, self).dispatch(*args, **kwargs)
        return ret

    @classonlymethod
    def as_view(cls, **initkwargs):
        """
        Django as_view cannot be used since the constructor requires information only present in the request.
        """
        raise Exception('as_view not supported for domain-specific ESView')
        
    @classonlymethod
    def as_domain_specific_view(cls, **initkwargs):
        """
        Creates a simple domain-specific class-based view for passing through ES requests.
        """
        def view(request, domain, *args, **kwargs):
            self = cls(domain)
            return self.dispatch(request, domain, *args, **kwargs)
        
        return view

    def run_query(self, es_query, es_type=None):
        """
        Run a more advanced POST based ES query

        Returns the raw query json back, or None if there's an error
        """
        
        logging.info("ESlog: [%s.%s] ESquery: %s" % (self.__class__.__name__, self.domain, simplejson.dumps(es_query)))
        if 'fields' in es_query or 'script_fields' in es_query:
            #nasty hack to add domain field to query that does specific fields.
            #do nothing if there's no field query because we get everything
            fields = es_query.get('fields', [])
            fields.append('domain')
            es_query['fields'] = fields

        es_base = self.es[self.index] if es_type is None else self.es[self.index][es_type]
        es_results = es_base.get('_search', data=es_query)

        if 'error' in es_results:
            msg = "Error in elasticsearch query [%s]: %s\nquery: %s" % (self.index, es_results['error'], es_query)
            notify_exception(None, message=msg)
            return None

        hits = []
        for res in es_results['hits']['hits']:
            if '_source' in res:
                res_domain = res['_source'].get('domain', None)
            elif 'fields' in res:
                res_domain = res['fields'].get('domain', None)

            # security check
            if res_domain == self.domain:
                hits.append(res)
            else:
                logging.info("Requester domain %s does not match result domain %s" % (
                    self.domain, res_domain))
        es_results['hits']['hits'] = hits
        return es_results

    def base_query(self, terms={}, fields=[], start=0, size=DEFAULT_SIZE):
        """
        The standard query to run across documents of a certain index.
        domain = exact match domain string
        terms = k,v pairs of terms you want to match against. you can dive down into properties like form.foo for an xform, like { "username": "foo", "type": "bar" } - this will make it into a term: k: v dict
        fields = field properties to report back in the results['fields'] array. if blank, you will need to read the _source
        start = where to start the results from
        size = default size in ES is 10, also explicitly set here.
        """
        query = {
            "filter": {
                "and": [
                    {"term": {"domain.exact": self.domain}}
                ]
            },
            "from": start,
            "size": size
        }
        if len(fields) > 0:
            query['fields'] = fields
        for k, v in terms.items():
            query['filter']['and'].append({"term": {k: v}})
        return query

    def get(self, *args, **kwargs):
        """
        Very basic querying based upon GET parameters.
        todo: apply GET params as lucene query_string params to base_query
        """
        size = self.request.GET.get('size', DEFAULT_SIZE)
        start = self.request.GET.get('start', 0)
        query_results = self.run_query(self.base_query(start=start, size=size))
        query_output = simplejson.dumps(query_results, indent=self.indent)
        response = HttpResponse(query_output, content_type="application/json")
        return response

    def post(self, *args, **kwargs):
        """
        More powerful ES querying using POST params.
        """
        try:
            raw_post = self.request.raw_post_data
            raw_query = simplejson.loads(raw_post)
        except Exception, ex:
            content_response = dict(message="Error parsing query request", exception=ex.message)
            response = HttpResponse(status=406, content=simplejson.dumps(content_response))
            return response

        #ensure that the domain is filtered in implementation
        domain = self.request.domain
        query_results = self.run_query(raw_query)
        query_output = simplejson.dumps(query_results, indent=self.indent)
        response = HttpResponse(query_output, content_type="application/json")
        return response


class CaseES(ESView):
    """
    Expressive CaseES interface. Yes, this is redundant with pieces of the v0_1.py CaseAPI - todo to merge these applications
    Which this should be the final say on ES access for Casedocs
    """
    index = "hqcases"

class FullCaseES(ESView):
    """
    Fully indexed case index elasticsearch endpoint.
    """
    index = "full_cases"



class XFormES(ESView):
    index = "xforms"

    def base_query(self, terms={}, doc_type='xforminstance', fields=[], start=0, size=DEFAULT_SIZE):
        """
        Somewhat magical enforcement that the basic query for XForms will only return XFormInstance
        docs by default.
        """
        new_terms = terms
        if 'doc_type' not in new_terms:
            #let the terms override the kwarg - the query terms trump the magic
            new_terms['doc_type'] = doc_type
        return super(XFormES, self).base_query(terms=new_terms, fields=fields, start=start, size=size)


    def run_query(self, es_query):
        es_results = super(XFormES, self).run_query(es_query)
        #hack, walk the results again, and if we have xmlns, populate human readable names
        # Note that `get_unknown_form_name` does not require the request, which is also
        # not necessarily available here. So `None` is passed here.
        form_filter = FormsByApplicationFilter(None, domain=self.domain)

        if es_results:
            for res in es_results.get('hits', {}).get('hits', []):
                if '_source' in res:
                    xmlns = res['_source'].get('xmlns', None)
                    name = None
                    if xmlns:
                        name = form_filter.get_unknown_form_name(xmlns, none_if_not_found=True)
                    if not name:
                        name = 'unknown' # try to fix it below but this will be the default
                        # fall back
                        try:
                            if res['_source']['form'].get('@name', None):
                                name = res['_source']['form']['@name']
                            else:
                                backup = res['_source']['form'].get('#type', 'data')
                                if backup != 'data':
                                    name = backup
                        except (TypeError, KeyError):
                            pass

                    res['_source']['es_readable_name'] = name
        return es_results





    @classmethod
    def by_case_id_query(cls, domain, case_id, terms={}, doc_type='xforminstance', date_field=None, startdate=None, enddate=None, date_format='%Y-%m-%d'):
        """
        Run a case_id query on both case properties (supporting old and new) for xforms.

        datetime options onsubmission ranges possible too by passing datetime startdate or enddate

        args:
        domain: string domain, required exact
        case_id: string
        terms: k,v of additional filters to apply as terms and block of filter
        doc_type: explicit xforminstance doc_type term query (only search active, legit items)
        date_field: string property of the xform submission you want to do date filtering, be sure to make sure that the field in question is indexed as a datetime
        startdate, enddate: datetime interval values
        date_format: string of the date format to filter based upon, defaults to yyyy-mm-dd
        """
        query = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {"term": {"domain.exact": domain.lower()}},
                            {"term": {"doc_type": doc_type}},
                        ]
                    },
                    "query": {
                        "query_string": {
                            "query": "(form.case.case_id:%(case_id)s OR form.case.@case_id:%(case_id)s)" % dict(
                                case_id=case_id)
                        }
                    }
                }
            }
        }
        if date_field is not None:
            range_query = {
                "numeric_range": {
                    date_field: {}
                }
            }

            if startdate is not None:
                range_query['numeric_range'][date_field]["gte"] = startdate.strftime(date_format)
            if enddate is not None:
                range_query['numeric_range'][date_field]["lte"] = enddate.strftime(date_format)
            query['query']['filtered']['filter']['and'].append(range_query)

        for k, v in terms.items():
            query['query']['filtered']['filter']['and'].append({"term": {k.lower(): v.lower()}})
        return query

class FullXFormES(XFormES):
    index = 'full_xforms'

class ESQuerySet(object):
    """
    An abstract representation of an elastic search query,
    modeled somewhat after Django's QuerySet but with
    the only important goal being compatibility
    with Tastypie's classes. Key capabilities, by piece of
    Tastypie:

    Pagination:

    - `__getitem__([start:stop])` which should efficiently pass the bounds on to ES
    - `count()` which should efficiently ask ES for the total matching (regardless of slice)

    Sorting:

    - Meh?

    Serialization:

    - `__iter__()`
    
    """

    # Also note https://github.com/llonchj/django-tastypie-elasticsearch/ which is
    # not very mature, plus this code below may involve Dimagic-specific assumptions
    
    def __init__(self, es_client, payload=None, model=None):
        """
        Instantiate with an entire ElasticSearch payload,
        since "query", "filter", etc, all exist alongside
        each other.
        """
        self.es_client = es_client
        self.payload = payload
        self.model = model
        self.__results = None

    def with_fields(self, es_client=None, payload=None, model=None):
        "Clones this queryset, optionally changing some fields"
        return ESQuerySet(es_client=es_client or self.es_client,
                          payload=payload or self.payload,
                          model=model or self.model)
        
    @property
    def results(self):
        if self.__results is None:
            self.__results = self.es_client.run_query(self.payload)
        return self.__results

    def count(self):
        # Just asks ES for the count by limiting results to zero, leveraging slice implementation
        return self[0:0].results['hits']['total']

    def __len__(self):
        # Note that this differs from `count` in that it actually performs the query and measures
        # only those objects returned
        return len(self.results['hits']['hits'])

    def __iter__(self):
        for jvalue in self.results['hits']['hits']:
            if self.model:
                # HACK: Sometimes the model is a class w/ a wrap method, sometimes just a function
                if hasattr(self.model, 'wrap'):
                    yield self.model.wrap(jvalue['_source']) 
                else:
                    yield self.model(jvalue['_source'])
            else:
                yield jvalue['_source']

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            if idx.start < 0 or idx.stop < 0:
                # This actually could be supported with varying degrees of efficiency
                raise NotImplementedError('Negative index in slice not supported.')

            new_payload = copy.deepcopy(self.payload)
            new_payload['from'] = new_payload.get('from', 0) + (idx.start or 0)

            if idx.stop is not None:
                new_payload['size'] = max(0, idx.stop - (idx.start or 0))

            return self.with_fields(payload=new_payload)

        elif isinstance(idx, six.integer_types):
            if idx >= 0:
                # Leverage efficicent backend slicing
                return list(self[idx:idx+1])[0]
            else:
                # This actually could be supported with varying degrees of efficiency
                raise NotImplementedError('Negative index not supported.')
        else:
            raise TypeError('Unsupported type: %s', type(idx))

RESERVED_QUERY_PARAMS=set(['limit', 'offset', 'q', '_search'])

# Note that dates are already in a string format when they arrive as query params
query_param_transforms = {
    'xmlns': lambda v: {'term':{'xmlns.exact':v}},
    'received_on_start': lambda v: {'range':{'received_on': {'from': v}}},
    'received_on_end': lambda v: {'range':{'received_on': {'to': v}}},
}

def es_search(request, domain):
    payload = {
        "filter": {
            "and": [
                {"term": {"domain.exact": domain}}
            ]
        },
    }

    # ?_search=<json> for providing raw ES query, which is nonetheless restricted here
    # NOTE: The fields actually analyzed into ES indices differ somewhat from the raw
    # XML / JSON.
    if '_search' in request.GET:
        additions = simplejson.loads(request.GET['_search'])

        if 'filter' in additions:
            payload['filter']['and'].append(additions['filter'])

        if 'query' in additions:
            payload['query'] = additions['query']

    # ?q=<lucene>
    if 'q' in request.GET:
        payload['query'] = payload.get('query', {})
        payload['query']['query_string'] = {'query': request.GET['q']} # A bit indirect?

    # filters are actually going to be a more common case
    for key in set(request.GET.keys()) - RESERVED_QUERY_PARAMS:
        if key.endswith('__full'): continue
        
        value = request.GET[key]

        if key in query_param_transforms:
            payload["filter"]["and"].append(query_param_transforms[key](value))
        else:
            payload["filter"]["and"].append({"term": {key: value}})


    return payload
