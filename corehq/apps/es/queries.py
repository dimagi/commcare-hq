import re


def match_all():
    """
    No-op query used because a default must be specified
    """
    return {"match_all": {}}


def _smart_query_string(query):
    special_chars = ['&&', '||', '!', '(', ')', '{', '}', '[', ']', '^', '"',
                     '~', '*', '?', ':', '\\', '/']
    for char in special_chars:
        if char in query:
            return False, query
    r = re.compile(r'\w+')
    tokens = r.findall(query)
    return True, "*{}*".format("* *".join(tokens))


def user_query_string(query, default_fields=None):
    """
    If query does not use the ES query string syntax,
    default to doing an infix search for each term.
    returns (is_simple, query)
    """
    if not query:
        return match_all()

    is_simple, query = _smart_query_string(query)
    return {
        "query_string": {
            "query": query,
            "default_operator": "AND",
            "fields": default_fields if is_simple else None
        }
    }
