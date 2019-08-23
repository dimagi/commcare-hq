"""
Available Queries
-----------------

Queries are used for actual searching - things like relevancy scores,
Levenstein distance, and partial matches.

View the `elasticsearch documentation <query_docs>`_ to see what other options
are available, and put 'em here if you end up using any of 'em.

.. _`query_docs`: https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-queries.html
"""
from .filters import range_filter, date_range
import re

MUST = "must"
MUST_NOT = "must_not"
SHOULD = "should"
BOOL = "bool"


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


def _smart_query_string(search_string):
    special_chars = ['&&', '||', '!', '(', ')', '{', '}', '[', ']', '^', '"',
                     '~', '*', '?', ':', '\\', '/']
    for char in special_chars:
        if char in search_string:
            return True, search_string
    r = re.compile(r'\w+')
    tokens = r.findall(search_string)
    return False, "*{}*".format("* *".join(tokens))


def search_string_query(search_string, default_fields=None):
    """
    Allows users to use advanced query syntax, but if ``search_string`` does
    not use the ES query string syntax, default to doing an infix search for
    each term.  (This may later change to some kind of fuzzy matching).

    This is also available via the main ESQuery class.
    """
    if not search_string:
        return match_all()

    # use simple_query_string for user-provided syntax, since it won't error
    uses_syntax, query_string = _smart_query_string(search_string)
    query_method = "simple_query_string" if uses_syntax else "query_string"
    return {
        query_method: {
            "query": query_string,
            "default_operator": "AND",
            "fields": default_fields if not uses_syntax else None,
        }
    }


def match(search_string, field, fuzziness="AUTO"):
    return {
        "match": {
            field: {
                "query": search_string,
                "fuzziness": fuzziness,
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


def nested_filter(path, filter_, *args, **kwargs):
    """
    Creates a nested query for use with nested documents

    Keyword arguments such as score_mode and others can be added.
    """
    nested = {
        "path": path,
        "filter": filter_
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
        "filtered": {
            "query": query,
            "filter": filter_,
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


range_query = range_filter
date_range = date_range
