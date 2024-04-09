"""
Available Queries
-----------------

Queries are used for actual searching - things like relevancy scores,
Levenstein distance, and partial matches.

View the `elasticsearch documentation <query_docs>`_ to see what other options
are available, and put 'em here if you end up using any of 'em.

.. _`query_docs`: https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-queries.html
"""
import re

from .filters import date_range, range_filter

MUST = "must"
MUST_NOT = "must_not"
SHOULD = "should"
BOOL = "bool"

DISTANCE_UNITS = ["miles", "yards", "feet", "inch", "kilometers", "meters",
                  "centimeters", "millimeters", "nauticalmiles"]


def BOOL_CLAUSE(query, **kwargs):
    return _CLAUSE(BOOL, query, **kwargs)


def MUST_CLAUSE(query, **kwargs):
    return _CLAUSE(MUST, query, **kwargs)


def MUST_NOT_CLAUSE(query, **kwargs):
    return _CLAUSE(MUST_NOT, query, **kwargs)


def SHOULD_CLAUSE(query, **kwargs):
    return _CLAUSE(SHOULD, query, **kwargs)


def _CLAUSE(clause, query, **kwargs):
    clause = {clause: query}
    clause.update(kwargs)
    return clause


CLAUSES = {
    MUST: MUST_CLAUSE,
    MUST_NOT: MUST_NOT_CLAUSE,
    SHOULD: SHOULD_CLAUSE,
    BOOL: BOOL_CLAUSE
}


def match_all():
    """No-op query used because a default must be specified"""
    return {"match_all": {}}


def search_string_query(search_string, default_fields):
    """
    All input defaults to doing an infix search for each term.
    (This may later change to some kind of fuzzy matching).

    This is also available via the main ESQuery class.
    """
    if not search_string:
        return match_all()

    # Parse user input into individual search terms
    r = re.compile(r'\w+')
    tokens = r.findall(search_string)
    query_string = "*{}*".format("* *".join(tokens))

    # TODO: add support for searching date ranges.

    return {
        "query_string": {
            "query": query_string,
            "default_operator": "AND",
            "fields": default_fields,
        }
    }


def ids_query(doc_ids):
    return {"ids": {"values": doc_ids}}


def match(search_string, field, operator=None):
    if operator not in [None, 'and', 'or']:
        raise ValueError(" 'operator' argument should be one of: 'and', 'or' ")
    return {
        "match": {
            field: {
                "query": search_string,
                # OR is the accepted default for the operator on an ES match query
                "operator": 'and' if operator == 'and' else 'or',
                "fuzziness": "0",
            }
        }
    }


def fuzzy(search_string, field, fuzziness="AUTO"):
    return {
        "fuzzy": {
            field: {
                "value": f"{search_string}".lower(),
                "fuzziness": fuzziness,
                "max_expansions": 100
            }
        }
    }


def nested(path, query, *args, **kwargs):
    """
    Creates a nested query for use with nested documents

    Keyword arguments such as score_mode and others can be added.
    """
    nested = {
        "path": path,
        "query": query
    }
    nested.update(kwargs)
    return {
        "nested": nested
    }


def filtered(query, filter_):
    """
    Filtered query for performing both filtering and querying at once
    """
    return {
        "bool": {
            "filter": [filter_],
            "must": query
        }
    }


def regexp(field, regex):
    return {
        'regexp': {
            field: {
                'value': regex,
            }
        }
    }


def geo_distance(field, geopoint, **kwargs):
    """Filters cases to those within a certain distance of the provided geopoint

        eg: geo_distance('gps_location', GeoPoint(-33.1, 151.8), kilometers=100)
    """
    if len(kwargs) != 1 or not all(k in DISTANCE_UNITS for k in kwargs):
        raise ValueError("'geo_distance' requires exactly one distance kwarg, "
                         f"options are {', '.join(DISTANCE_UNITS)}")
    unit, distance = kwargs.popitem()

    return {
        'geo_distance': {
            field: geopoint.lat_lon,
            'distance': f"{distance}{unit}",
        }
    }


range_query = range_filter
date_range = date_range
