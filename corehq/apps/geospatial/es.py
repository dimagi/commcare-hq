from math import ceil

from corehq.apps.case_search.const import CASE_PROPERTIES_PATH
from corehq.apps.es import filters
from corehq.apps.es.aggregations import (
    FilterAggregation,
    GeohashGridAggregation,
    NestedAggregation,
)
from corehq.apps.es.case_search import PROPERTY_GEOPOINT_VALUE, PROPERTY_KEY
from corehq.apps.geospatial.const import MAX_GEOHASH_DOC_COUNT

AGG_NAME = 'geohashes'


def find_precision(query, case_property):
    """
    Uses a binary search to find the value for ``precision`` that
    maximizes geohash doc count but does not exceed
    ``MAX_GEOHASH_DOC_COUNT``.

    (A lower value of ``precision`` will increase the doc count, and a
    higher value will decrease it.)
    """
    lower = 1
    upper = 12
    while True:
        precision = mid(lower, upper)
        max_doc_count = get_max_doc_count(query, case_property, precision)
        if max_doc_count > MAX_GEOHASH_DOC_COUNT and precision > lower:
            # Increase next value of precision to decrease doc count
            lower = precision
        elif max_doc_count < MAX_GEOHASH_DOC_COUNT and precision < upper:
            # Decrease next value of precision to increase doc count
            upper = precision
        else:
            # max_doc_count == MAX_GEOHASH_DOC_COUNT
            # or upper and lower are equal or adjacent
            return precision


def get_max_doc_count(query, case_property, precision):
    query = query.clone()
    query = apply_geohash_agg(query, case_property, precision)
    queryset = query.run()
    # queryset.raw should include something similar to the following.
    # The length of the bucket "key" value will be determined by the
    # value of `precision`. In the example below, the length of the key
    # is 3 because `precision` is 3.
    #
    #     'aggregations': {
    #         'case_properties': {
    #             'case_property': {
    #                 'doc_count': 6,
    #                 'geohashes': {
    #                     'buckets': [
    #                         {
    #                           "key": "u17",
    #                           "doc_count": 3
    #                         },
    #                         {
    #                           "key": "u09",
    #                           "doc_count": 2
    #                         },
    #                         {
    #                           "key": "u15",
    #                           "doc_count": 1
    #                         }
    #                     ]
    #                 }
    #             }
    #         }
    #     }
    buckets = (
        queryset.raw['aggregations']
        ['case_properties']
        ['case_property']
        [AGG_NAME]
        ['buckets']
    )
    return max(bucket['doc_count'] for bucket in buckets) if buckets else 0


def apply_geohash_agg(query, case_property, precision):
    nested_agg = NestedAggregation('case_properties', CASE_PROPERTIES_PATH)
    filter_agg = FilterAggregation(
        'case_property',
        filters.term(PROPERTY_KEY, case_property),
    )
    geohash_agg = GeohashGridAggregation(
        AGG_NAME,
        PROPERTY_GEOPOINT_VALUE,
        precision,
    )
    return query.aggregation(
        nested_agg.aggregation(
            filter_agg.aggregation(
                geohash_agg
            )
        )
    )


def mid(lower, upper):
    """
    Returns the integer midpoint between ``lower`` and ``upper``.

    >>> mid(4, 6)
    5
    >>> mid(4, 5)
    5
    """
    assert lower <= upper
    return ceil(lower + (upper - lower) / 2)
