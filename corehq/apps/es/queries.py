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


def match_all():
    """No-op query used because a default must be specified"""
    return {"match_all": {}}


def _smart_query_string(search_string):
    special_chars = ['&&', '||', '!', '(', ')', '{', '}', '[', ']', '^', '"',
                     '~', '*', '?', ':', '\\', '/']
    for char in special_chars:
        if char in search_string:
            return False, search_string
    r = re.compile(r'\w+')
    tokens = r.findall(search_string)
    return True, "*{}*".format("* *".join(tokens))


def search_string_query(search_string, default_fields=None):
    """
    Allows users to use advanced query syntax, but if ``search_string`` does
    not use the ES query string syntax, default to doing an infix search for
    each term.  (This may later change to some kind of fuzzy matching).

    This is also available via the main ESQuery class.
    """
    if not search_string:
        return match_all()

    is_simple, query_string = _smart_query_string(search_string)
    return {
        "query_string": {
            "query": query_string,
            "default_operator": "AND",
            "fields": default_fields if is_simple else None
        }
    }
