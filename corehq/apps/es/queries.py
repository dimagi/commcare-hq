import re


def match_all():
    """
    No-op query used because a default must be specified
    """
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
    If search_string does not use the ES query string syntax,
    default to doing an infix search for each term.
    returns (is_simple, query)
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
