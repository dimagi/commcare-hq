from typing import Callable, Optional

from corehq.apps.es import CaseSearchES
from corehq.apps.es.aggregations import GeohashGridAggregation
from corehq.apps.es.case_search import case_property_geo_bounding_box
from corehq.apps.es.es_query import ESQuery
from couchforms.geopoint import GeoPoint

AGG_NAME = 'geohashes'
MAX_DOC_COUNT = 10_000


def get_geohashes(
    domain: str,
    *,
    field: str,
    top_left: GeoPoint,
    bottom_right: GeoPoint,
    precision: Optional[int] = None,
) -> tuple[ESQuery, int]:
    """
    Queries Elasticsearch for geohash grid aggregations of cases.

    :param domain: The domain name
    :param field: The case property to search
    :param top_left: Top-left coordinates of the bounding box
    :param bottom_right: Bottom-right coordinates of the bounding box
    :param precision: The geohash precision. If ``None``, the correct
        precision will be determined such that the aggregation doc
        count < 10,000
    :return: An ESQuery and its precision
    """
    query = (
        CaseSearchES()
        .domain(domain)
        .set_query(
            case_property_geo_bounding_box(field, top_left, bottom_right)
        )
    )
    # TODO: ...
    # if precision is None:
    #     # Find the lowest value of ``precision`` between 1 and 12 that
    #     # returns less than 10,000 cases
    #     test_func = partial(_geohash_search_test, query, field)
    #     precision = find_lowest(1, 12, test_func)
    query = query.aggregation(
        GeohashGridAggregation(AGG_NAME, field, precision)
    )
    return query, precision


def _geohash_search_test(query, field, precision):
    query = query.clone()
    query = query.aggregation(
        GeohashGridAggregation(AGG_NAME, field, precision)
    )
    queryset = query.run()
    # {
    #   ...
    #   "aggregations": {
    #     AGG_NAME: {
    #       "buckets": [
    #         {
    #           "key": "u17",
    #           "doc_count": 3
    #         },
    #         {
    #           "key": "u09",
    #           "doc_count": 2
    #         },
    #         {
    #           "key": "u15",
    #           "doc_count": 1
    #         }
    #       ]
    #     }
    #   }
    # }
    buckets = queryset.aggregations.geohashes.raw_buckets
    # TODO: Don't do this           ^^^^^^^^^
    return all(bucket['doc_count'] < MAX_DOC_COUNT for bucket in buckets)


def mid(lower: int, upper: int) -> int:
    """
    Returns the integer midpoint between ``lower`` and ``upper``.

    >>> mid(1,3)
    2
    >>> mid(1,4)
    2
    >>> mid(1,5)
    3
    """
    assert lower < upper
    return lower + (upper - lower) // 2


def find_lowest(
    lower_bound: int,
    upper_bound: int,
    test_func: Callable[[int], bool],
    last_true: Optional[int] = None,  # TODO: last_false?
) -> Optional[int]:
    """
    Uses a binary search to find the lowest value between
    ``lower_bound`` and ``upper_bound`` for which ``test_func`` returns
    ``True``.

    :param lower_bound: The minimum candidate value
    :param upper_bound: The maximum candidate value
    :param test_func: A function that takes a candidate value, and
        returns ``True`` if the value passes, and ``False`` if it fails.
    :param last_true: When searching for the first ``False`` result,
        this passes the candidate that produced the last ``True``
        result.
    :return: The candidate value that was found, or None.
    """
    if lower_bound == upper_bound:
        return None

    midpoint = mid(lower_bound, upper_bound)
    if test_func(midpoint):
        # if find_lowest:
        #     # TODO: Keep going
        #     pass
        # else:
        return midpoint
    return find_lowest(midpoint, upper_bound, test_func)

