"""
TODOs:
Figure out proper default_filters for each class
make filter be match_all if all defaults are removed
pagination
sorting
date filter
"""
from copy import deepcopy
import json

from ..elastic import ES_URLS, ESError, run_query

from . import filters


class ESQuery(object):
    """
    {"query": {
        "filtered": {
            "filter": {
                "and": [
                    <filters>
                ]
            },
            "query": <query>
        }
    }}

    language:
        es_query - the entire query, filters, query, pagination, facets
        filters - a list of the individual filters
        query - the query, used for searching, not filtering
        field - a field on the document. User docs have a 'domain' field.
        lt/gt - less/greater than
        lte/gte - less/greater than or equal to
    """
    _result = None
    index = None
    fields = None
    start = None
    size = None
    default_filters = {
        'match_all': {'match_all': {}}
    }

    def __init__(self, index=None):
        self.index = index or self.index
        if self.index not in ES_URLS:
            msg = "%s is not a valid ES index.  Available options are: %s" % (
                index, ', '.join(ES_URLS.keys()))
            raise IndexError(msg)
        self.es_query = {"query": {
            "filtered": {
                "filter": {"and": []},
                "query": {'match_all': {}}
            }
        }}
        # when the filters are needed, add remaining default filters and query

    def result(self):
        if self._result is not None:
            return self._result
        self._result = run_query(self.url, self.raw_query)
        if 'error' in self._result:
            msg = ("ElasticSearch Error\n{error}\nIndex: {index}\nURL:{url}"
                   "\nQuery: {query}").format({
                       'error': self._result['error'],
                       'index': self.index,
                       'url': self.url,
                       'query': self.dumps(pretty=True)
                    })
            raise ESError(msg)
        return self._result

    def raw_hits(self):
        return self.result()['hits']['hits']

    def hits(self):
        if self.fields is not None:
            hits = [r['fields'] for r in self.raw_hits()['hits']['hits']]
        else:
            hits = [r['_source'] for r in self.raw_hits()['hits']['hits']]

    def total(self):
        # TODO don't run full query if it hasn't been run already
        # run query with size=0
        return self.result()['hits']['total']

    @property
    def _filters(self):
        return self.es_query['query']['filtered']['filter']['and']

    def add_filter(self, filter):
        query = deepcopy(self)
        query._filters.append(filter)
        return query

    @property
    def filters(self):
        return self.default_filters + self._filters

    @property
    def _query(self):
        return self.es_query['query']['filtered']['query']

    @property
    def set_query(self, query):
        es = deepcopy(self)
        es.es_query['query']['filtered']['query'] = query
        return es

    def assemble(self):
        """
        build out the es_query dict
        """
        self._filters.append(self.default_filters)
        if self.fields is not None:
            self.es_query['fields'] = self.fields
        if self.start is not None:
            self.es_query['start'] = self.start
        if self.size is not None:
            self.es_query['size'] = self.size

    @property
    def raw_query(self):
        query = deepcopy(self)
        query.assemble()
        return query.es_query

    def dumps(self, pretty=False):
        indent = 4 if pretty else None
        return json.dumps(self.raw_query, indent=indent)

    def pprint(self):
        print self.dumps(pretty=True)

    @property
    def url(self):
        return ES_URLS[self.index],

    def sort(self, field, desc=False):
        query = deepcopy(self)
        query.es_query['sort'] = {
            field: {'order': 'desc' if desc else 'asc'}
        }
        return query

    def is_normal(self):
        try:
            self.es_query['query']['filtered']['filter']['and']
            self.es_query['query']['filtered']['query']
        except (KeyError, AssertionError):
            raise ESError("In order to use this method, your query must be "
                          "in the format specified in the ESQuery class")
        else:
            return True

    def remove_default_filter(self, default):
        query = deepcopy(self)
        query.default_filters.pop(default)
        return query

    def fuzzy_query(self, q):
        self.set_query({"fuzzy_like_this": {"like_text": q}})

    def term(self, field, value):
        return self.add_filter(filters.term(field, value))

    def OR(self, **filters):
        return self.add_filter(filters.OR(**filters))

    def range(self, field, gt=None, gte=None, lt=None, lte=None):
        return self.add_filter(filters.range_filter(field, gt, gte, lt, lte))

    def date_range(self, field, gt=None, gte=None, lt=None, lte=None):
        return  self.add_filter(filters.date_range(field, gt, gte, lt, lte))


class HQESQuery(ESQuery):
    """
    Query logic specific to CommCareHQ
    """
    def doc_type(self, doc_type):
        return self.term('doc_type', doc_type)

    def domain(self, domain):
        return self.term('domain.exact', domain)


class UserES(HQESQuery):
    index = 'users'
    default_filters = {
        'mobile_worker': {"term": {"doc_type": "CommCareUser"}},
        'not_deleted': {"term": {"base_doc": "couchuser"}},
        'active': {"term": {"is_active": True}},
    }

    def domain(self, domain):
        self.OR(
            filters.term("domain.exact", domain),
            filters.term("domain_memberships.domain.exact", domain)
        )

    def show_inactive(self):
        return self.remove_default_filter('active')


class FormsES(HQESQuery):
    index = 'forms'
    default_filters = {
        'is_xform_instance': {"term": {"doc_type": "xforminstance"}},
        'has_xmlns': {"not": {"missing": {"field": "xmlns"}}},
        'has_user': {"not": {"missing": {"field": "form.meta.userID"}}},
    }

    def submitted(self, gt=None, gte=None, lt=None, lte=None):
        return self.date_range('received_on', gt, gte, lt, lte)

    def completed(self, gt=None, gte=None, lt=None, lte=None):
        return self.date_range('form.meta.timeEnd', gt, gte, lt, lte)

    def xmlns(self, xmlns):
        return self.term('xmlns.exact', xmlns)

    def app(self, app_id):
        return self.term('app_id', app_id)


class Example(object):
    def example_query(self):
        q = FormsES()\
            .domain(self.domain)\
            .xmlns(self.xmlns)\
            .submitted(gte=self.datespan.startdate_param,
                       lt=self.datespan.enddateparam)\
            .sort('received_on', desc=False)

        total_docs = q.total()
        hits = q.page(start=self.pagination.start, size=self.pagination.count)\
                .hits()
