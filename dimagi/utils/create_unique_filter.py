
def create_unique_filter(fn):
    """Returns a filter that applies fn to an object and returns
    true if it's a new value, otherwise false. useful for filtering
    lists dynamically based on some other conditional.
    >>> import random
    >>> l = [{'id': 'a'}, {'id': 'b'}, {'id': 'a'}, {'id': 'c'}, {'id': 'b'}]
    >>> filter(create_unique_filter(lambda x: x['id']), l)
    [{'id': 'a'}, {'id': 'b'}, {'id': 'c'}]
    >>> filter(create_unique_filter(lambda x: id(x)), l)
    [{'id': 'a'}, {'id': 'b'}, {'id': 'a'}, {'id': 'c'}, {'id': 'b'}]
    """

    unique = set()
    def filter(x):
        res = fn(x)
        if res in unique:
            return False
        unique.add(res)
        return True
    return filter
