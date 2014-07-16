"""
TODOs:
Figure out proper default_filters for each class
make filter be match_all if all defaults are removed
sorting
Add esquery.iter() method
"""
from copy import deepcopy
import json

from corehq.elastic import ES_URLS, ESError, run_query

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
    index = None
    _fields = None
    _start = None
    _size = None
    default_filters = {
        "match_all": {"match_all": {}}
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

    @property
    def builtin_filters(self):
        """
        A list of callables that return filters
        These will all be available as instance methods, so you can do
            self.term(field, value)
        instead of
            self.filter(filters.term(field, value))
        """
        return [
            filters.term,
            filters.OR,
            filters.AND,
            filters.range_filter,
            filters.date_range,
        ]

    def __getattr__(self, attr):
        # This is syntactic sugar
        # If you do query.<attr> and attr isn't found as a classmethod,
        # this will look for it in self.builtin_filters.
        for fn in self.builtin_filters:
            if fn.__name__ == attr:
                def add_filter(*args, **kwargs):
                    return self.filter(fn(*args, **kwargs))
                return add_filter
        raise AttributeError("There is no builtin filter named %s" % attr)

    def run(self):
        raw = run_query(self.url, self.raw_query)
        if 'error' in raw:
            msg = ("ElasticSearch Error\n{error}\nIndex: {index}\nURL:{url}"
                   "\nQuery: {query}").format(
                       error=raw['error'],
                       index=self.index,
                       url=self.url,
                       query=self.dumps(pretty=True),
                    )
            raise ESError(msg)
        return ESQuerySet(raw, deepcopy(self))

    @property
    def _filters(self):
        return self.es_query['query']['filtered']['filter']['and']

    def filter(self, filter):
        query = deepcopy(self)
        query._filters.append(filter)
        return query

    @property
    def filters(self):
        return self.default_filters.values() + self._filters

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
        self._filters.extend(self.default_filters.values())
        if self._fields is not None:
            self.es_query['fields'] = self._fields
        if self._start is not None:
            self.es_query['start'] = self._start
        if self._size is not None:
            self.es_query['size'] = self._size

    def fields(self, fields):
        # analagous to sql offset
        query = deepcopy(self)
        query._fields = fields
        return query

    def start(self, start):
        # analagous to sql offset
        query = deepcopy(self)
        query._start = start
        return query

    def size(self, size):
        # analagous to SQL limit
        query = deepcopy(self)
        query._size = size
        return query

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
        return ES_URLS[self.index]

    def sort(self, field, desc=False):
        query = deepcopy(self)
        query.es_query['sort'] = {
            field: {'order': 'desc' if desc else 'asc'}
        }
        return query

    def remove_default_filter(self, default):
        query = deepcopy(self)
        query.default_filters.pop(default)
        return query


class ESQuerySet(object):
    """
    The object returned from ESQuery.run
    ESQuerySet.raw is the raw response from elasticsearch
    ESQuerySet.query is the ESQuery object
    """
    def __init__(self, raw, query):
        self.raw = raw
        self.query = query

    def raw_hits(self):
        return self.raw['hits']['hits']

    @property
    def hits(self):
        if self.query._fields is not None:
            return [r['fields'] for r in self.raw_hits()]
        else:
            return [r['_source'] for r in self.raw_hits()]

    @property
    def total(self):
        return self.raw['hits']['total']


class HQESQuery(ESQuery):
    """
    Query logic specific to CommCareHQ
    """
    @property
    def builtin_filters(self):
        return [
            filters.domain,
            filters.doc_type,
        ] + super(HQESQuery, self).builtin_filters
