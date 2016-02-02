"""
Aggregate Queries
---------------
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
add support for other facet types and more results processing
"""
import re
from collections import namedtuple

from corehq.apps.es import filters


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
    def buckets(self):
        buckets = namedtuple('buckets', [b['key'] for b in self.raw_buckets])
        return buckets(**{b['key']: Bucket(b, self._aggregations) for b in self.raw_buckets})

    @property
    def buckets_dict(self):
        return {b['key']: Bucket(b, self._aggregations) for b in self.raw_buckets}

    @property
    def raw_buckets(self):
        return self.result['buckets']

    @property
    def counts_by_bucket(self):
        return {b['key']: b['doc_count'] for b in self.raw_buckets}


class Bucket(object):
    def __init__(self, result, aggregations):
        self.result = result
        self.aggregations = aggregations

    @property
    def key(self):
        return self.result['key']

    @property
    def doc_count(self):
        return self.result['doc_count']

    def __getattr__(self, attr):
        sub_aggregation = filter(lambda a: a.name == attr, self.aggregations)[0]
        if sub_aggregation:
            return sub_aggregation.parse_result(self.result)


class TermsAggregation(Aggregation):
    """
    Bucket aggregation that aggregates by field

    :param name: aggregation name
    :param field: name of the field to bucket on
    """
    type = "terms"
    result_class = BucketResult

    def __init__(self, name, field):
        assert re.match(r'\w+$', name), \
            "Names must be valid python variable names, was {}".format(name)
        self.name = name
        self.body = {
            "field": field,
        }


class FilterResult(AggregationResult):
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

    def __init__(self, name):
        self.name = name
        self.body = {"filters": {}}

    def add_filter(self, name, filter):
        """
        :param name: filter name
        :param filter: filter body
        """
        self.body["filters"][name] = filter
        return self
