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


def match_none():
    return {"match_none": {}}


def prefix(field, value):
    return {"prefix": {field: value}}


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


def nested(path, *filters):
    """Query nested documents which normally can't be queried directly"""
    return {
        "nested": {
            "path": path,
            "query": {
                "bool": {
                    "filter": filters
                }
            }
        }
    }


def regexp(field, regex):
    return {"regexp": {field: regex}}


def geo_bounding_box(field, top_left, bottom_right):
    """
    Only return geopoints stored in ``field`` that are located within
    the bounding box defined by ``top_left`` and ``bottom_right``.

    ``top_left`` and ``bottom_right`` accept a range of data types and
    formats.

    More info: `Geo Bounding Box Query <https://www.elastic.co/guide/en/elasticsearch/reference/5.6/query-dsl-geo-bounding-box-query.html>`_
    """  # noqa: E501
    return {
        'geo_bounding_box': {
            field: {
                'top_left': top_left,
                'bottom_right': bottom_right,
            }
        }
    }


def geo_polygon(field, points):
    """
    Filters ``geo_point`` values in ``field`` that fall within the
    polygon described by the list of ``points``.

    More info: `Geo Polygon Query <https://www.elastic.co/guide/en/elasticsearch/reference/5.6/query-dsl-geo-polygon-query.html>`_

    :param field: A field with Elasticsearch data type ``geo_point``.
    :param points: A list of points that describe a polygon.
        Elasticsearch supports a range of formats for list items.
    :return: A filter dict.
    """  # noqa: E501
    # NOTE: Deprecated in Elasticsearch 7.12
    return {
        'geo_polygon': {
            field: {
                'points': points,
            }
        }
    }


def geo_shape(field, shape, relation='intersects'):
    """
    Filters cases by case properties indexed using the ``geo_point``
    type.

    More info: `The Geoshape query reference <https://www.elastic.co/guide/en/elasticsearch/reference/8.10/query-dsl-geo-shape-query.html>`_

    :param field: The field where geopoints are stored
    :param shape: A shape definition given in GeoJSON geometry format.
        More info: `The GeoJSON specification (RFC 7946) <https://datatracker.ietf.org/doc/html/rfc7946>`_
    :param relation: The relation between the shape and the case
        property values.
    :return: A filter definition
    """  # noqa: E501
    # NOTE: Available in Elasticsearch 8+.
    #
    # The geoshape query is available in Elasticsearch 5.6, but only
    # supports the `geo_shape` type (not the `geo_point` type), which
    # CommCare HQ does not use.

    # TODO: After Elasticsearch is upgraded, switch from geo_polygon to
    #       geo_shape. (Norman, 2023-11-01)
    # e.g.
    #
    #     geo_polygon(field, points)
    #
    # becomes
    #
    #     shape = {
    #         'type': 'polygon',
    #         'coordinates': points,
    #     }
    #     geo_shape(field, shape, relation='within')
    #
    return {
        "geo_shape": {
            field: {
                "shape": shape,
                "relation": relation
            }
        }
    }


def geo_grid(field, geohash):
    """
    Filters cases by the geohash grid cell in which they are located.
    """
    # Available in Elasticsearch 8+
    return {
        "geo_grid": {
            field: {
                "geohash": geohash
            }
        }
    }
