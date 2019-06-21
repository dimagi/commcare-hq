"""
Aggregate Queries
-----------------
Aggregations are a replacement for Facets

Here is an example used to calculate how many new pregnancy cases each user has
opened in a certain date range.

.. code-block:: python

    res = (CaseES()
           .domain(self.domain)
           .case_type('pregnancy')
           .date_range('opened_on', gte=startdate, lte=enddate))
           .aggregation(TermsAggregation('by_user', 'opened_by')
           .size(0)

    buckets = res.aggregations.by_user.buckets
    buckets.user1.doc_count

There's a bit of magic happening here - you can access the raw json data from
this aggregation via ``res.aggregation('by_user')`` if you'd prefer to skip it.

The ``res`` object has a ``aggregations`` property, which returns a namedtuple
pointing to the wrapped aggregation results.  The name provided at instantiation is
used here (``by_user`` in this example).

The wrapped ``aggregation_result`` object has a ``result`` property containing the
aggregation data, as well as utilties for parsing that data into something more
useful. For example, the ``TermsAggregation`` result also has a ``counts_by_bucket``
method that returns a ``{bucket: count}`` dictionary, which is normally what you
want.

As of this writing, there's not much else developed, but it's pretty easy to
add support for other aggregation types and more results processing
"""
from __future__ import absolute_import
from __future__ import unicode_literals
from copy import deepcopy
import re
from collections import namedtuple, defaultdict

import datetime

from corehq.elastic import SIZE_LIMIT
import six
from six.moves import filter

from corehq.util.python_compatibility import soft_assert_type_text

MISSING_KEY = None


class AggregationResult(object):

    def __init__(self, raw, aggregation):
        self.aggregation = aggregation
        self.raw = raw
        self.result = raw.get(self.aggregation.name, {})
        self._aggregations = self.aggregation.aggregations


class Aggregation(object):
    name = None
    type = None
    body = None
    result_class = AggregationResult
    aggregations = None

    def __init__(self):
        raise NotImplementedError()

    def aggregation(self, aggregation):
        if not self.aggregations:
            self.aggregations = []

        self.aggregations.append(aggregation)
        return self

    def assemble(self):
        if self.type == "case_property":
            assembled = self.body
        else:
            assembled = {self.type: self.body}

        if self.aggregations:
            assembled['aggs'] = {}
            for agg in self.aggregations:
                assembled['aggs'][agg.name] = agg.assemble()

        return assembled

    def parse_result(self, result):
        return self.result_class(result, self)


class BucketResult(AggregationResult):

    @property
    def keys(self):
        return [b['key'] for b in self.normalized_buckets]

    @property
    def buckets(self):
        n_buckets = self.normalized_buckets
        buckets = namedtuple('buckets', [b['key'] for b in n_buckets])
        return buckets(**{b['key']: Bucket(b, self._aggregations) for b in n_buckets})

    @property
    def buckets_dict(self):
        return {b['key']: Bucket(b, self._aggregations) for b in self.normalized_buckets}

    @property
    def buckets_list(self):
        return [Bucket(b, self._aggregations) for b in self.normalized_buckets]

    @property
    def raw_buckets(self):
        return self.result['buckets']

    @property
    def normalized_buckets(self):
        return self.raw_buckets

    def counts_by_bucket(self):
        return {b['key']: b['doc_count'] for b in self.normalized_buckets}


class MissingResult(AggregationResult):

    @property
    def bucket(self):
        return Bucket(self.result, self._aggregations)


class TopHitsResult(AggregationResult):

    @property
    def raw_hits(self):
        return self.result['hits']['hits']

    @property
    def doc_ids(self):
        """Return just the docs ids from the response."""
        return [r['_id'] for r in self.raw_hits]

    @property
    def hits(self):
        """Return the docs from the response."""
        return [r['_source'] for r in self.raw_hits]

    @property
    def total(self):
        """Return the total number of docs matching the query."""
        return self.result['hits']['total']


class StatsResult(AggregationResult):

    @property
    def count(self):
        return self.result['count']

    @property
    def max(self):
        return self.result['max']

    @property
    def min(self):
        return self.result['min']

    @property
    def avg(self):
        return self.result['avg']


class ExtendedStatsResult(StatsResult):

    @property
    def std_dev(self):
        return self.result['std_deviation']


class Bucket(object):

    def __init__(self, result, aggregations):
        self.result = result
        self.aggregations = aggregations

    @property
    def key(self):
        return self.result.get('key', MISSING_KEY)

    @property
    def doc_count(self):
        return self.result['doc_count']

    def __getattr__(self, attr):
        sub_aggregation = list(filter(lambda a: a.name == attr, self.aggregations))[0]
        if sub_aggregation:
            return sub_aggregation.parse_result(self.result)

    def __repr__(self):
        return "Bucket(key='{}', doc_count='{}')".format(self.key, self.doc_count)


class TermsAggregation(Aggregation):
    """
    Bucket aggregation that aggregates by field

    :param name: aggregation name
    :param field: name of the field to bucket on
    :param size:
    """
    type = "terms"
    result_class = BucketResult

    def __init__(self, name, field, size=None):
        assert re.match(r'\w+$', name), \
            "Names must be valid python variable names, was {}".format(name)
        self.name = name
        self.body = {
            "field": field,
            "size": size if size is not None else SIZE_LIMIT,
        }

    def order(self, field, order="asc", reset=True):
        query = deepcopy(self)
        order_field = {field: order}

        if reset:
            query.body['order'] = [order_field]
        else:
            if not query.body.get('order'):
                query.body['order'] = []
            query.body['order'].append(order_field)

        return query

    def size(self, size):
        query = deepcopy(self)
        query.body['size'] = size
        return query


class SumResult(AggregationResult):

    @property
    def value(self):
        return self.result['value']


class SumAggregation(Aggregation):
    """
    Bucket aggregation that sums a field

    :param name: aggregation name
    :param field: name of the field to sum
    """
    type = "sum"
    result_class = SumResult

    def __init__(self, name, field):
        assert re.match(r'\w+$', name), \
            "Names must be valid python variable names, was {}".format(name)
        self.name = name
        self.body = {
            "field": field,
        }


class MinAggregation(SumAggregation):
    """
    Bucket aggregation that returns the minumum value of a field

    :param name: aggregation name
    :param field: name of the field to min
    """
    type = "min"


class MaxAggregation(SumAggregation):
    type = "max"


class AvgAggregation(SumAggregation):
    type = "avg"


class ValueCountAggregation(SumAggregation):
    type = "value_count"


class CardinalityAggregation(SumAggregation):
    type = "cardinality"


class MissingAggregation(Aggregation):
    """
    A field data based single bucket aggregation, that creates a bucket of all
    documents in the current document set context that are missing a field value
    (effectively, missing a field or having the configured NULL value set).

    :param name: aggregation name
    :param field: name of the field to bucket on
    """
    type = "missing"
    result_class = MissingResult

    def __init__(self, name, field):
        assert re.match(r'\w+$', name), \
            "Names must be valid python variable names, was {}".format(name)
        self.name = name
        self.body = {"field": field}


class StatsAggregation(Aggregation):
    """
    Stats aggregation that computes a stats aggregation by field

    :param name: aggregation name
    :param field: name of the field to collect stats on
    :param script: an optional field to allow you to script the computed field
    """
    type = "stats"
    result_class = StatsResult

    def __init__(self, name, field, script=None):
        assert re.match(r'\w+$', name), \
            "Names must be valid python variable names, was {}".format(name)
        self.name = name
        self.body = {"field": field}
        if script:
            self.body.update({'script': script})


class ExtendedStatsAggregation(StatsAggregation):
    """
    Extended stats aggregation that computes an extended stats aggregation by field
    """
    type = "extended_stats"
    result_class = ExtendedStatsResult


class TopHitsAggregation(Aggregation):
    """
    A top_hits metric aggregator keeps track of the most relevant document being aggregated
    This aggregator is intended to be used as a sub aggregator, so that the top matching
    documents can be aggregated per bucket.

    :param name: Aggregation name
    :param field: This is the field to sort the top hits by. If None, defaults to sorting
        by score.
    :param is_ascending: Whether to sort the hits in ascending or descending order.
    :param size: The number of hits to include. Defaults to 1.
    :param include: An array of fields to include in the hit. Defaults to returning the whole document.
    """
    type = "top_hits"
    result_class = TopHitsResult

    def __init__(self, name, field=None, is_ascending=True, size=1, include=None):
        assert re.match(r'\w+$', name), \
            "Names must be valid python variable names, was {}".format(name)
        self.name = name
        self.body = {
            'size': size,
        }
        if field:
            self.body["sort"] = [{
                field: {
                    "order": 'asc' if is_ascending else 'desc'
                },
            }]
        if include:
            self.body["_source"] = {"include": include}


class FilterResult(AggregationResult):

    def __getattr__(self, attr):
        sub_aggregation = list([a for a in self._aggregations if a.name == attr])[0]
        if sub_aggregation:
            return sub_aggregation.parse_result(self.result)

    @property
    def doc_count(self):
        return self.result['doc_count']


class FilterAggregation(Aggregation):
    """
    Bucket aggregation that creates a single bucket for the specified filter

    :param name: aggregation name
    :param filter: filter body
    """
    type = "filter"
    result_class = FilterResult

    def __init__(self, name, filter):
        self.name = name
        self.body = filter


class FiltersAggregation(Aggregation):
    """
    Bucket aggregation that creates a bucket for each filter specified using
    the filter name.

    :param name: aggregation name
    """
    type = "filters"
    result_class = BucketResult

    def __init__(self, name, filters=None):
        self.name = name
        self.body = {"filters": (filters or {})}

    def add_filter(self, name, filter):
        """
        :param name: filter name
        :param filter: filter body
        """
        self.body["filters"][name] = filter
        return self


class AggregationRange(namedtuple('AggregationRange', 'start end key')):
    """
    Note that a range includes the "start" value and excludes the "end" value.
    i.e. start <= X < end

    :param start: range start
    :param end: range end
    :param key: optional key name for the range
    """
    def __new__(cls, start=None, end=None, key=None):
        assert start or end, "At least one of 'from' or 'to' are required"
        return super(AggregationRange, cls).__new__(cls, start, end, key)

    def assemble(self):
        range_ = {}
        for key, attr in {'from': 'start', 'to': 'end', 'key': 'key'}.items():
            value = getattr(self, attr)
            if value:
                if isinstance(value, datetime.date):
                    value = value.isoformat()
                elif not isinstance(value, six.string_types):
                    value = six.text_type(value)
                else:
                    soft_assert_type_text(value)
                range_[key] = value
        return range_


class RangeResult(BucketResult):

    @property
    def normalized_buckets(self):
        buckets = self.raw_buckets
        if self.aggregation.keyed:
            def _add_key(key, bucket):
                bucket['key'] = key
                return bucket
            return [_add_key(k, b) for k, b in buckets.items()]
        else:
            def _add_key(bucket):
                key = '{}-{}'.format(bucket.get('from', '*'), bucket.get('to', '*'))
                bucket['key'] = key
                return bucket

            return [_add_key(b) for b in buckets]


class RangeAggregation(Aggregation):
    """
    Bucket aggregation that creates one bucket for each range
    :param name: the aggregation name
    :param field: the field to perform the range aggregations on
    :param ranges: list of AggregationRange objects
    :param keyed: set to True to have the results returned by key instead of as
    a list (see RangeResult.normalized_buckets)
    """
    type = "range"
    result_class = RangeResult

    def __init__(self, name, field, ranges=None, keyed=True):
        self.keyed = keyed
        self.name = name
        self.body = {
            'field': field,
            'keyed': keyed,
            'ranges': []
        }
        if ranges:
            for range_ in ranges:
                self.add_range(range_)

    def add_range(self, range_):
        if isinstance(range_, AggregationRange):
            range_ = range_.assemble()

        if range_.get('key'):
            self.body['keyed'] = True

        self.body["ranges"].append(range_)
        return self


class HistogramResult(BucketResult):

    def as_facet_result(self):
        return [
            {'time': b.key, 'count': b.doc_count}
            for b in self.buckets_list
        ]


class DateHistogram(Aggregation):
    """
    Aggregate by date range.  This can answer questions like "how many forms
    were created each day?".

    This class can be instantiated by the ``ESQuery.date_histogram`` method.

    :param name: what do you want to call this aggregation
    :param datefield: the document's date field to look at
    :param interval: the date interval to use: "year", "quarter", "month",
        "week", "day", "hour", "minute", "second"
    :param timezone: do bucketing using this time zone instead of UTC
    """
    type = "date_histogram"
    result_class = HistogramResult

    def __init__(self, name, datefield, interval, timezone=None):
        self.name = name
        self.body = {
            'field': datefield,
            'interval': interval,
        }

        if timezone:
            self.body['time_zone'] = timezone


class NestedAggregation(Aggregation):
    """
    A special single bucket aggregation that enables aggregating nested documents.

    :param path: Path to nested document
    """
    type = "nested"
    result_class = FilterResult

    def __init__(self, name, path):
        self.name = name
        self.body = {
            "path": path
        }


AggregationTerm = namedtuple('AggregationTerm', ['name', 'field'])


class NestedTermAggregationsHelper(object):
    """
    Helper to run nested term-based queries (equivalent to SQL group-by clauses).
    This is not at all related to the ES 'nested aggregation'. The final aggregation
    defaults to a count of documents, though can also be used to sum a different field
    of the document.

    Example usage:

    .. code-block:: python

        # counting all forms submitted in a domain grouped by app id and user id

        NestedTermAggregationsHelper(
            base_query=FormES().domain(domain_name),
            terms=[
                AggregationTerm('app_id', 'app_id'),
                AggregationTerm('user_id', 'form.meta.userID'),
            ]
        ).get_data()

        # summing the balances of ledger values, grouped by the entry id

        NestedTermAggregationsHelper(
            base_query=LedgerES().domain(domain).section(section_id),
            terms=[
                AggregationTerm('entry_id', 'entry_id'),
            ],
            inner_most_aggregation=SumAggregation('balance', 'balance'),
        ).get_data()

    This works by bucketing docs first by one terms aggregation, then within
    that bucket, bucketing further by the next term, and so on. This is then
    flattened out to appear like a group-by-multiple.
    """

    def __init__(self, base_query, terms, inner_most_aggregation=None):
        self.base_query = base_query
        self.terms = terms
        self.inner_most_aggregation = inner_most_aggregation

    @property
    def query(self):
        previous_term = None

        if self.inner_most_aggregation is not None:
            if not isinstance(self.inner_most_aggregation, SumAggregation):
                raise ValueError('currently only SumAggregations and its children are supported')
            term = self.inner_most_aggregation
            previous_term = term

        for name, field in reversed(self.terms):
            term = TermsAggregation(name, field)
            if previous_term is not None:
                term = term.aggregation(previous_term)
            previous_term = term

        return self.base_query.aggregation(term)

    def get_data(self):
        def _add_terms(aggregation_bucket, term, remaining_terms, current_counts, current_key=None):
            for bucket in getattr(aggregation_bucket, term.name).buckets_list:
                key = (bucket.key,) if current_key is None else current_key + (bucket.key,)
                if remaining_terms:
                    _add_terms(bucket, remaining_terms[0], remaining_terms[1:], current_counts, current_key=key)
                else:
                    # base case
                    if self.inner_most_aggregation is None:
                        current_counts[key] += bucket.doc_count
                    else:
                        current_counts[key] += getattr(bucket, self.inner_most_aggregation.name).value

        counts = defaultdict(lambda: 0)
        _add_terms(self.query.size(0).run().aggregations, self.terms[0], self.terms[1:], current_counts=counts)
        return self._format_counts(counts)

    def _format_counts(self, counts):
        final_aggregation_name = ('doc_count' if self.inner_most_aggregation is None
                                  else self.inner_most_aggregation.name)
        row_class = namedtuple('NestedQueryRow', [term.name for term in self.terms] + [final_aggregation_name])
        for combined_key, count in counts.items():
            yield row_class(*(combined_key + (count,)))
