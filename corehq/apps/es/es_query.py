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
         .source(['xmlns', 'domain', 'app_id'])
         .sort('received_on', desc=False)
         .size(self.pagination.count)
         .start(self.pagination.start)
         .terms_aggregation('babies.count', 'babies_saved'))
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

 * es_query - the entire query, filters, query, pagination
 * filters - a list of the individual filters
 * query - the query, used for searching, not filtering
 * field - a field on the document. User docs have a 'domain' field.
 * lt/gt - less/greater than
 * lte/gte - less/greater than or equal to

.. TODOs:
    sorting
    Add esquery.iter() method
"""
import json
from collections import namedtuple
from copy import deepcopy
import textwrap

from memoized import memoized

from corehq.util.files import TransientTempfile

from . import aggregations, filters, queries
from .const import SCROLL_SIZE, SIZE_LIMIT
from .exceptions import ESError
from .transient_util import doc_adapter_from_cname
from .utils import flatten_field_dict, values_list


class InvalidQueryError(Exception):
    """Query parameters cannot be assembled into a valid search."""


class ESQuery(object):
    """
    This query builder only outputs the following query structure::

        {
          "query": {
            "bool": {
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
    # `index` is actually a canonical name (which may be the same as the alias)
    index = None
    _exclude_source = None
    _legacy_fields = False
    _start = None
    _size = None
    _aggregations = None
    _source = None
    default_filters = {
        "match_all": filters.match_all()
    }

    def __init__(self, index=None, for_export=False):
        if index is None:
            index = self.index  # use class attribute
        self.adapter = doc_adapter_from_cname(index, for_export=for_export)
        self._default_filters = deepcopy(self.default_filters)
        self._aggregations = []
        self.es_query = {
            "query": {
                "bool": {
                    "filter": [],
                    "must": queries.match_all()
                }
            }
        }

    def clone(self):
        adapter = self.adapter
        del self.adapter  # don't deep copy the adapter
        try:
            cloned = deepcopy(self)
        finally:
            self.adapter = adapter
        cloned.adapter = adapter
        return cloned

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
            filters.regexp,
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

    def __getitem__(self, sliced_or_int):
        if isinstance(sliced_or_int, int):
            start = sliced_or_int
            size = 1
        else:
            start = sliced_or_int.start or 0
            size = sliced_or_int.stop - start
        return self.start(start).size(size).run().hits

    def run(self):
        """Actually run the query.  Returns an ESQuerySet object."""
        return ESQuerySet(self.adapter.search(self.raw_query), self.clone())

    def scroll(self):
        """
        Run the query against the scroll api. Returns an iterator yielding each
        document that matches the query.
        """
        if self.uses_aggregations():
            raise InvalidQueryError(
                "aggregation scroll queries will yield invalid hits if the "
                "scroll requires more than one request."
            )
        raw_query = self.raw_query
        raw_query["size"] = SCROLL_SIZE if self._size is None else self._size
        # The '_assemble()' method sets size=SIZE_LIMIT when no query size is
        # configured, and overrides that with size=0 for aggregation queries,
        # neither of which are acceptable for a scroll query.
        for result in self.adapter.scroll(raw_query):
            yield ESQuerySet.normalize_result(self, result)

    @property
    def _filters(self):
        return self.es_query['query']['bool']['filter']

    def exclude_source(self):
        """
        Turn off _source retrieval. Mostly useful if you just want the doc_ids
        """
        self._exclude_source = True
        return self

    def filter(self, filter):
        """
        Add the passed-in filter to the query.  All filtering goes through
        this class.
        """
        query = self.clone()
        query._filters.append(filter)
        return query

    @property
    def filters(self):
        """
        Return a list of the filters used in this query, suitable if you
        want to reproduce a query with additional filtering.
        """
        return list(self._default_filters.values()) + self._filters

    def uses_aggregations(self):
        return len(self._aggregations) > 0

    def aggregation(self, aggregation):
        """
        Add the passed-in aggregation to the query
        """
        query = self.clone()
        query._aggregations.append(aggregation)
        return query

    def aggregations(self, aggregations):
        query = self.clone()
        query._aggregations.extend(aggregations)
        return query

    def terms_aggregation(self, term, name, size=None, sort_field=None, order="asc"):
        agg = aggregations.TermsAggregation(name, term, size=size)
        if sort_field:
            agg = agg.order(sort_field, order)
        return self.aggregation(agg)

    @property
    def _query(self):
        return self.es_query['query']['bool']['must']

    def set_query(self, query):
        """
        Set the query.  Most stuff we want is better done with filters, but
        if you actually want Levenshtein distance or prefix querying...
        """
        es = self.clone()
        es.es_query['query']['bool']['must'] = query
        return es

    def enable_profiling(self):
        self.es_query['profile'] = True
        return self

    def add_query(self, new_query, clause):
        """
        Add a query to the current list of queries
        """
        current_query = self._query.get(queries.BOOL)
        if current_query is None:
            return self.set_query(
                queries.BOOL_CLAUSE(
                    queries.CLAUSES[clause]([new_query])
                )
            )
        elif current_query.get(clause) and isinstance(current_query[clause], list):
            current_query[clause] += [new_query]
        else:
            current_query.update(
                queries.CLAUSES[clause]([new_query])
            )
        return self

    def get_query(self):
        return self.es_query['query']['bool']['must']

    def search_string_query(self, search_string, default_fields):
        """Accepts a user-defined search string"""
        return self.set_query(
            queries.search_string_query(search_string, default_fields)
        )

    def fields(self, fields):
        """
            Restrict the fields returned from elasticsearch

            Deprecated. Use `source` instead.
            """
        self._legacy_fields = True
        return self.source(fields)

    def ids_query(self, doc_ids):
        return self.set_query(
            queries.ids_query(doc_ids)
        )

    def source(self, include, exclude=None):
        """
            Restrict the output of _source in the queryset. This can be used to return an object in a queryset
        """
        self._exclude_source = False

        source = include
        if exclude:
            source = {
                'include': include,
                'exclude': exclude
            }
        query = self.clone()
        query._source = source
        return query

    def start(self, start):
        """Pagination.  Analagous to SQL offset."""
        query = self.clone()
        query._start = start
        return query

    def size(self, size):
        """Restrict number of results returned. Analagous to SQL limit, except
        when performing a scroll, in which case this value becomes the number of
        results to fetch per scroll request.
        """
        query = self.clone()
        query._size = size
        return query

    @property
    def raw_query(self):
        query = self.clone()
        query._assemble()
        return query.es_query

    def _assemble(self):
        """Build out the es_query dict"""
        self._filters.extend(list(self._default_filters.values()))
        if self._start is not None:
            self.es_query['from'] = self._start
        self.es_query['size'] = self._size if self._size is not None else SIZE_LIMIT
        if self._exclude_source:
            self.es_query['_source'] = False
        elif self._source is not None:
            self.es_query['_source'] = self._source
        if self.uses_aggregations():
            self.es_query['size'] = 0  # Just return the aggs, not the hits
            self.es_query['aggs'] = {
                agg.name: agg.assemble()
                for agg in self._aggregations
            }

    def dumps(self, pretty=False):
        """Returns the JSON query that will be sent to elasticsearch."""
        indent = 4 if pretty else None
        return json.dumps(self.raw_query, indent=indent)

    def pprint(self):
        """pretty prints the JSON query that will be sent to elasticsearch."""
        print(self.dumps(pretty=True))

    def _sort(self, sort, reset_sort):
        query = self.clone()
        if reset_sort:
            query.es_query['sort'] = [sort]
        else:
            if not query.es_query.get('sort'):
                query.es_query['sort'] = []
            query.es_query['sort'].append(sort)

        return query

    def sort(self, field, desc=False, reset_sort=True):
        """Order the results by field."""
        assert field != '_id', "Cannot sort on reserved _id field"
        sort_field = {
            field: {'order': 'desc' if desc else 'asc'}
        }
        return self._sort(sort_field, reset_sort)

    def nested_sort(self, path, field_name, nested_filter, desc=False, reset_sort=True, sort_missing=None):
        """Order results by the value of a nested field
        """
        sort_field = {
            '{}.{}'.format(path, field_name): {
                'order': 'desc' if desc else 'asc',
                'nested_path': path,
                'nested_filter': nested_filter,
                'missing': sort_missing,
            }
        }
        return self._sort(sort_field, reset_sort)

    def set_sorting_block(self, sorting_block):
        """To be used with `get_sorting_block`, which interprets datatables sorting"""
        query = self.clone()
        query.es_query['sort'] = sorting_block
        return query

    def remove_default_filters(self):
        """Sensible defaults are provided.  Use this if you don't want 'em"""
        query = self.clone()
        query._default_filters = {"match_all": filters.match_all()}
        return query

    def remove_default_filter(self, default):
        """Remove a specific default filter by passing in its name."""
        query = self.clone()
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
        if kwargs.pop('scroll', False):
            hits = self.fields(fields).scroll()
        else:
            hits = self.fields(fields).run().hits

        return values_list(hits, *fields, **kwargs)

    def count(self):
        return self.adapter.count(self.raw_query)

    def get_ids(self):
        """Performs a minimal query to get the ids of the matching documents

        For very large sets of IDs, use ``scroll_ids`` instead"""
        return self.exclude_source().run().doc_ids

    def scroll_ids(self):
        """Returns a generator of all matching ids"""
        return self.exclude_source().scroll()

    def scroll_ids_to_disk_and_iter_docs(self):
        """Returns a ``ScanResult`` for all matched documents.

        Used for iterating docs for a very large query where consuming the docs
        via ``self.scroll()`` may exceed the amount of time that the scroll
        context can remain open. This is achieved by:

        1. Fetching the IDs for all matched documents (via ``scroll_ids()``) and
           caching them in a temporary file on disk, then
        2. fetching the documents by (chunked blocks of) IDs streamed from the
           temporary file.

        Original design PR: https://github.com/dimagi/commcare-hq/pull/20282

        Caveats:
        - There is no guarantee that the returned ScanResult's ``count``
        property will match the number of yielded docs.
        - Documents that are present when ``scroll_ids()`` is called, but are
        deleted prior to being fetched in full will be missing from the
        results, and this scenario will *not* raise an exception.
        - If Elastic document ID values are ever reused (i.e. new documents
        are created with the same ID of a previously-deleted document) then
        this method would become unsafe because it could yield documents that
        were not matched by the query.
        """
        def iter_export_docs():
            with TransientTempfile() as temp_path:
                # Write all ids to disk as quickly as ES scrolls them
                with open(temp_path, 'w', encoding='utf-8') as stream:
                    for doc_id in self.scroll_ids():
                        stream.write(doc_id + '\n')
                # Stream doc ids from disk and fetch documents from ES in chunks
                with open(temp_path, 'r', encoding='utf-8') as stream:
                    doc_ids = (doc_id.strip() for doc_id in stream)
                    yield from self.adapter.iter_docs(doc_ids)
        return ScanResult(self.count(), iter_export_docs())


class ScanResult(object):

    def __init__(self, count, iterator):
        self._iterator = iterator
        self.count = count

    def __iter__(self):
        yield from self._iterator


class ESQuerySet(object):
    """
    The object returned from ``ESQuery.run``
     * ESQuerySet.raw is the raw response from elasticsearch
     * ESQuerySet.query is the ESQuery object
    """

    def __init__(self, raw, query):
        if 'error' in raw:
            msg = textwrap.dedent(f"""
                ElasticSearch Error
                {raw['error']}
                Index: {query.index}
                Query: {query.dumps(pretty=True)}""").lstrip()

            raise ESError(msg)
        self.raw = raw
        self.query = query

    @staticmethod
    def normalize_result(query, result):
        """Return the doc from an item in the query response."""
        if query._exclude_source:
            return result['_id']
        if query._legacy_fields:
            return flatten_field_dict(result, fields_property='_source')
        else:
            return result['_source']

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
        if self.query.uses_aggregations():
            raise ESError("We exclude hits for aggregation queries")

        return [self.normalize_result(self.query, r) for r in self.raw_hits]

    @property
    def total(self):
        """Return the total number of docs matching the query."""
        return self.raw['hits']['total']

    def aggregation(self, name):
        return self.raw['aggregations'][name]

    @property
    @memoized
    def aggregations(self):
        aggregations = self.query._aggregations
        raw = self.raw.get('aggregations', {})
        results = namedtuple('aggregation_results', [a.name for a in aggregations])
        return results(**{a.name: a.parse_result(raw) for a in aggregations})

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
