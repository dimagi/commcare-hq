def dicts_or(*dicts):
    """
    Returns a dictionary of key-values from d1 | d2 | d3 ...

    >>> foo = {1: 'one', 2: 'two'}
    >>> bar = {2: 'deux', 3: 'trois'}
    >>> baz = {3: 'drie', 4: 'vier'}
    >>> dicts_or(foo, bar, baz)
    {1: 'one', 2: 'two', 3: 'trois', 4: 'vier'}

    """
    assert len(dicts), "No operands"
    if len(dicts) == 1:
        return dicts[0]
    d1 = dicts[0]
    dn = dicts_or(*dicts[1:])
    return {k: d1[k] if k in d1 else dn[k] for k in d1.keys() | dn.keys()}
