
def find_difference(a, b):
    """
    Returns set ``b`` - set ``a``, and set ``a`` - set ``b``
    >>> find_difference([1, 2, 3], [3, 4, 5])
    ({4, 5}, {1, 2})
    """
    return set(b).difference(set(a)), set(a).difference(set(b))
