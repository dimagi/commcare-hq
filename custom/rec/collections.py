def dicts_or(*dicts):
    """
    Returns a dictionary of key-values from d1 | d2 | d3 ...

    >>> foo = {1: 'one', 2: 'two'}
    >>> bar = {2: 'deux', 3: 'trois'}
    >>> baz = {3: 'drie', 4: 'vier'}
    >>> dicts_or(foo, bar, baz) == {1: 'one', 2: 'two', 3: 'trois', 4: 'vier'}
    True

    """
    return {k: v for d in dicts[::-1] for k, v in d.items()}
