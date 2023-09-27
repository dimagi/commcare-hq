"""
Available Filters
-----------------

The following filters are available on any ESQuery instance - you can chain
any of these on your query.

Note also that the ``term`` filter accepts either a list or a single element.
Simple filters which match against a field are based on this filter, so those
will also accept lists.
That means you can do ``form_query.xmlns(XMLNS1)`` or
``form_query.xmlns([XMLNS1, XMLNS2, ...])``.

Contributing:
Additions to this file should be added to the ``builtin_filters`` method on
either ESQuery or HQESQuery, as appropriate (is it an HQ thing?).
"""
from .utils import es_format_datetime


def match_all():
    return {"match_all": {}}


def prefix(field, value):
    return {"prefix": {field: value}}


def wildcard(field, value):
    return {"wildcard": {field: value}}


def term(field, value):
    """
    Filter docs by a field
    'value' can be a singleton or a list.
    """
    if isinstance(value, list):
        return {"terms": {field: value}}
    elif isinstance(value, tuple):
        return {"terms": {field: list(value)}}
    elif isinstance(value, set):
        return {"terms": {field: list(value)}}
    else:
        return {"term": {field: value}}


def OR(*filters):
    """Filter docs to match any of the filters passed in"""
    return {"bool": {"should": filters}}


def AND(*filters):
    """Filter docs to match all of the filters passed in"""
    return {"bool": {"filter": filters}}


def NOT(filter_):
    """Exclude docs matching the filter passed in"""
    return {"bool": {"must_not": filter_}}


def not_term(field, value):
    return NOT(term(field, value))


def range_filter(field, gt=None, gte=None, lt=None, lte=None):
    """
    Filter ``field`` by a range.  Pass in some sensible combination of ``gt``
    (greater than), ``gte`` (greater than or equal to), ``lt``, and ``lte``.
    """
    return {"range": {field: {
        k: v for k, v in {'gt': gt, 'gte': gte, 'lt': lt, 'lte': lte}.items()
        if v is not None
    }}}


def date_range(field, gt=None, gte=None, lt=None, lte=None):
    """Range filter that accepts date and datetime objects as arguments"""
    params = [d if d is None else es_format_datetime(d) for d in [gt, gte, lt, lte]]
    return range_filter(field, *params)


def domain(domain_name):
    """Filter by domain."""
    return term('domain.exact', domain_name)


def doc_type(doc_type):
    """Filter by doc_type.  Also accepts a list"""
    return term('doc_type', doc_type)


def doc_id(doc_id):
    """Filter by doc_id.  Also accepts a list of doc ids"""
    return term("_id", doc_id)


def missing(field):
    """Only return docs missing a value for ``field``"""
    return NOT(exists(field))


def exists(field):
    """Only return docs which have a value for ``field``"""
    return {"exists": {"field": field}}


def empty(field):
    """Only return docs with a missing or null value for ``field``"""
    return OR(missing(field), term(field, ''))


def non_null(field):
    """Only return docs with a real, non-null value for ``field``"""
    return NOT(empty(field))


def nested(path, filter_):
    """Query nested documents which normally can't be queried directly"""
    return {
        "nested": {
            "path": path,
            "query": {
                "bool": {
                    "filter": filter_
                }
            }
        }
    }


def regexp(field, regex):
    return {"regexp": {field: regex}}


def geo_bounding_box(field, top_left, bottom_right):
    """
    Only return geopoints stored in ``field`` that are located within
    the bounding box defined by GeoPoints ``top_left`` and
    ``bottom_right``.

    `"Geo-bounding box query" reference <https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-geo-bounding-box-query.html>`_

    :param field: The field where geopoints are stored
    :param top_left: The GeoPoint of the top left of the bounding box,
        a string in the format "latitude longitude" or "latitude
        longitude altitude accuracy"
    :param bottom_right: The GeoPoint of the bottom right of the
        bounding box
    :return: A filter dict
    """  # noqa: E501
    from couchforms.geopoint import GeoPoint

    top_left_geo = GeoPoint.from_string(top_left, flexible=True)
    bottom_right_geo = GeoPoint.from_string(bottom_right, flexible=True)
    return {
        'geo_bounding_box': {
            field: {
                'top_left': top_left_geo.lat_lon,
                'bottom_right': bottom_right_geo.lat_lon,
            }
        }
    }
