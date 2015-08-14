from corehq.apps.users.util import smart_query_string


def user_query_string(query, default_fields=None):
    """
    If query does not use the ES query string syntax,
    default to doing an infix search for each term.
    returns (is_simple, query)
    """
    is_simple, query = smart_query_string(query)
    return {
        "query_string": {
            "query": query,
            "default_operator": "AND",
            #  "fields": default_fields if is_simple else None
        }
    }
