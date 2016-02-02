"""
ESQuery
=======

ESQuery is a library for building elasticsearch queries in a friendly,
more readable manner.

Basic usage
-----------

There should be a file and subclass of ESQuery for each index we have.

Each method returns a new object, so you can chain calls together like
SQLAlchemy. Here's an example usage:

.. code-block:: python

    q = (FormsES()
         .domain(self.domain)
         .xmlns(self.xmlns)
         .submitted(gte=self.datespan.startdate_param,
                    lt=self.datespan.enddateparam)
         .fields(['xmlns', 'domain', 'app_id'])
         .sort('received_on', desc=False)
         .size(self.pagination.count)
         .start(self.pagination.start)
         .terms_facet('babies.count', 'babies_saved', size=10))
    result = q.run()
    total_docs = result.total
    hits = result.hits

Generally useful filters and queries should be abstracted away for re-use,
but you can always add your own like so:

.. code-block:: python

    q.filter({"some_arbitrary_filter": {...}})
    q.set_query({"fancy_query": {...}})

For debugging or more helpful error messages, you can use ``query.dumps()``
and ``query.pprint()``, both of which use ``json.dumps()`` and are suitable for
pasting in to ES Head or Marvel or whatever

Filtering
---------

Filters are implemented as standalone functions, so they can be composed and
nested ``q.OR(web_users(), mobile_users())``.
Filters can be passed to the ``query.filter`` method: ``q.filter(web_users())``

There is some syntactic sugar that lets you skip this boilerplate and just
call the filter as if it were a method on the query class:  ``q.web_users()``
In order to be available for this shorthand, filters are added to the
``builtin_filters`` property of the main query class.
I know that's a bit confusing, but it seemed like the best way to make filters
available in both contexts.

Generic filters applicable to all indices are available in
``corehq.apps.es.filters``.  (But most/all can also be accessed as a query
method, if appropriate)

Filtering Specific Indices
--------------------------

There is a file for each elasticsearch index (if not, feel free to add one).
This file provides filters specific to that index, as well as an
appropriately-directed ESQuery subclass with references to these filters.

These index-specific query classes also have default filters to exclude things
like inactive users or deleted docs.
These things should nearly always be excluded, but if necessary, you can remove
these with ``remove_default_filters``.

Language
--------

 * es_query - the entire query, filters, query, pagination, facets
 * filters - a list of the individual filters
 * query - the query, used for searching, not filtering
 * field - a field on the document. User docs have a 'domain' field.
 * lt/gt - less/greater than
 * lte/gte - less/greater than or equal to

.. TODOs:
    sorting
    Add esquery.iter() method
"""
from collections import namedtuple
from copy import deepcopy
import json
from corehq.apps.es.utils import values_list, flatten_field_dict

from dimagi.utils.decorators.memoized import memoized

from corehq.elastic import ES_META, ESError, run_query, SIZE_LIMIT

from . import facets
from . import filters
from . import queries


class ESQuery(object):
    """
    This query builder only outputs the following query structure::

        {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            <filters>
                        ]
                    },
                    "query": <query>
                }
            },
            <size, sort, other params>
        }
    """
    index = None
    _fields = None
    _start = None
    _size = None
    _facets = None
    _source = None
    default_filters = {
        "match_all": filters.match_all()
    }

    def __init__(self, index=None):
        self.index = index if index is not None else self.index
        if self.index not in ES_META:
            msg = "%s is not a valid ES index.  Available options are: %s" % (
                index, ', '.join(ES_META.keys()))
            raise IndexError(msg)
        self._default_filters = deepcopy(self.default_filters)
        self._facets = []
        self._source = []
        self.es_query = {"query": {
            "filtered": {
                "filter": {"and": []},
                "query": queries.match_all()
            }
        }}

    @property
    def builtin_filters(self):
        """
        A list of callables that return filters. These will all be available as
        instance methods, so you can do ``self.term(field, value)`` instead of
        ``self.filter(filters.term(field, value))``
        """
        return [
            filters.term,
            filters.OR,
            filters.AND,
            filters.NOT,
            filters.range_filter,
            filters.date_range,
            filters.missing,
            filters.exists,
            filters.empty,
            filters.non_null,
            filters.doc_id,
            filters.nested,
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
        """Actually run the query.  Returns an ESQuerySet object."""
        raw = run_query(self.index, self.raw_query)
        return ESQuerySet(raw, deepcopy(self))

    @property
    def _filters(self):
        return self.es_query['query']['filtered']['filter']['and']

    def filter(self, filter):
        """
        Add the passed-in filter to the query.  All filtering goes through
        this class.
        """
        query = deepcopy(self)
        query._filters.append(filter)
        return query

    @property
    def filters(self):
        """
        Return a list of the filters used in this query, suitable if you
        want to reproduce a query with additional filtering.
        """
        return self._default_filters.values() + self._filters

    def facet(self, _facet):
        """Add a facet to the query."""
        query = deepcopy(self)
        query._facets.append(_facet)
        return query

    def terms_facet(self, term, name, size=None):
        return self.facet(facets.TermsFacet(term, name, size))

    def date_histogram(self, name, datefield, interval, timezone=None):
        return self.facet(facets.DateHistogram(name, datefield, interval, timezone=None))

    @property
    def _query(self):
        return self.es_query['query']['filtered']['query']

    def set_query(self, query):
        """
        Add a query.  Most stuff we want is better done with filters, but
        if you actually want Levenshtein distance or prefix querying...
        """
        es = deepcopy(self)
        es.es_query['query']['filtered']['query'] = query
        return es

    def search_string_query(self, search_string, default_fields=None):
        """Accepts a user-defined search string"""
        return self.set_query(
            queries.search_string_query(search_string, default_fields)
        )

    def _assemble(self):
        """Build out the es_query dict"""
        self._filters.extend(self._default_filters.values())
        if self._fields is not None:
            self.es_query['fields'] = self._fields
        if self._start is not None:
            self.es_query['from'] = self._start
        self.es_query['size'] = self._size if self._size is not None else SIZE_LIMIT
        if self._facets:
            self.es_query['facets'] = {
                facet.name: {facet.type: facet.params}
                for facet in self._facets
            }
        if self._source:
            self.es_query['_source'] = self._source

    def fields(self, fields):
        """
            Restrict the fields returned from elasticsearch

            Usage Note: As of ES 1.x, fields will only work on leaf nodes! It will no longer return an object,
            e.g. field.*, to return an object refer to '.source'
            """
        query = deepcopy(self)
        query._fields = fields
        return query

    def source(self, source):
        """
            Restrict the output of _source in the queryset. This can be used to return an object in a queryset

            TODO: How does this interact with .fields
        """
        query = deepcopy(self)
        query._source.append(source)
        return query

    def start(self, start):
        """Pagination.  Analagous to SQL offset."""
        query = deepcopy(self)
        query._start = start
        return query

    def size(self, size):
        """Restrict number of results returned.  Analagous to SQL limit."""
        query = deepcopy(self)
        query._size = size
        return query

    @property
    def raw_query(self):
        query = deepcopy(self)
        query._assemble()
        return query.es_query

    def dumps(self, pretty=False):
        """Returns the JSON query that will be sent to elasticsearch."""
        indent = 4 if pretty else None
        return json.dumps(self.raw_query, indent=indent)

    def pprint(self):
        """pretty prints the JSON query that will be sent to elasticsearch."""
        print self.dumps(pretty=True)

    def sort(self, field, desc=False):
        """Order the results by field."""
        query = deepcopy(self)
        query.es_query['sort'] = {
            field: {'order': 'desc' if desc else 'asc'}
        }
        return query

    def remove_default_filters(self):
        """Sensible defaults are provided.  Use this if you don't want 'em"""
        query = deepcopy(self)
        query._default_filters = {"match_all": filters.match_all()}
        return query

    def remove_default_filter(self, default):
        """Remove a specific default filter by passing in its name."""
        query = deepcopy(self)
        if default in query._default_filters:
            query._default_filters.pop(default)
        if len(query._default_filters) == 0:
            query._default_filters = {"match_all": filters.match_all()}
        return query

    def values(self, *fields):
        """modeled after django's QuerySet.values"""
        if fields:
            return self.fields(fields).run().hits
        else:
            return self.run().hits

    def values_list(self, *fields, **kwargs):
        return values_list(self.fields(fields).run().hits, *fields, **kwargs)

    def count(self):
        """Performs a minimal query to get the count of matching documents"""
        return self.size(0).run().total


class ESQuerySet(object):
    """
    The object returned from ``ESQuery.run``
     * ESQuerySet.raw is the raw response from elasticsearch
     * ESQuerySet.query is the ESQuery object
    """
    def __init__(self, raw, query):
        if 'error' in raw:
            msg = ("ElasticSearch Error\n{error}\nIndex: {index}"
                   "\nQuery: {query}").format(
                       error=raw['error'],
                       index=query.index,
                       query=query.dumps(pretty=True),
                    )
            raise ESError(msg)
        self.raw = raw
        self.query = query

    @property
    def raw_hits(self):
        return self.raw['hits']['hits']

    @property
    def doc_ids(self):
        """Return just the docs ids from the response."""
        return [r['_id'] for r in self.raw_hits]

    @property
    def hits(self):
        """Return the docs from the response."""
        if self.query._fields == []:
            return self.ids
        elif self.query._fields is not None:
            return [flatten_field_dict(r) for r in self.raw_hits]
        else:
            return [r['_source'] for r in self.raw_hits]

    @property
    def total(self):
        """Return the total number of docs matching the query."""
        return self.raw['hits']['total']

    @property
    def ids(self):
        return [r['_id'] for r in self.raw_hits]

    @property
    def raw_facets(self):
        return self.raw['facets']

    def facet(self, name, _type):
        return self.raw['facets'][name][_type]

    @property
    @memoized
    def facets(self):
        """
        Namedtuple of the facets defined in the query.
        See the facet docs for more specifics.
        """
        facets = self.query._facets
        raw = self.raw.get('facets', {})
        results = namedtuple('facet_results', [f.name for f in facets])
        return results(**{f.name: f.parse_result(raw) for f in facets})

    def __repr__(self):
        return '{}({!r}, {!r})'.format(self.__class__.__name__, self.raw, self.query)


class HQESQuery(ESQuery):
    """
    Query logic specific to CommCareHQ
    """
    @property
    def builtin_filters(self):
        return [
            filters.doc_id,
            filters.doc_type,
            filters.domain,
        ] + super(HQESQuery, self).builtin_filters
