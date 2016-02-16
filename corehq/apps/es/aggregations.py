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
add support for other aggregation types and more results processing
"""
import re
from collections import namedtuple

import datetime

from corehq.elastic import SIZE_LIMIT


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
        return {Bucket(b, self._aggregations) for b in self.normalized_buckets}

    @property
    def raw_buckets(self):
        return self.result['buckets']

    @property
    def normalized_buckets(self):
        return self.raw_buckets

    def counts_by_bucket(self):
        return {b['key']: b['doc_count'] for b in self.normalized_buckets}


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

    def __repr__(self):
        return "Bucket(key='{}', doc_count='{})".format(self.key, self.doc_count)


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
                elif not isinstance(value, basestring):
                    value = unicode(value)
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
    :param keyed: set to True to have the results returned by key instead of as a list
                  (see RangeResult.normalized_buckets)
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
