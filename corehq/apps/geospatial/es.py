from typing import Optional

from corehq.apps.es.es_query import ESQuery

AGG_NAME = 'geohashes'


def get_geohashes(
    domain: str,
    *,
    field: str,
    precision: Optional[int] = None,
    top_left: Optional[str] = None,
    bottom_right: Optional[str] = None,
) -> tuple[ESQuery, int]:
    """
    Queries Elasticsearch for geohash grid aggregations of cases.

    :param domain: The domain name
    :param field: The case property to search
    :param precision: The geohash precision. If ``None``, the correct
        precision will be determined such that the aggregation doc
        count < 10,000
    :param top_left: Top-left coordinates of an optional bounding box
    :param bottom_right: Bottom-right coordinates of an optional
        bounding box
    :return: An ESQuerySet and its precision
    """
