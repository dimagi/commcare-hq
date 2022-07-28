def slash_join(*strings):
    """
    Joins strings with a single ``/``.

    >>> slash_join('http://example.com', 'foo')
    'http://example.com/foo'
    >>> slash_join('http://example.com/', '/foo/')
    'http://example.com/foo/'

    """
    if len(strings) == 0:
        return ''
    if len(strings) == 1:
        return strings[0]
    left = [strings[0].rstrip('/')]
    right = [strings[-1].lstrip('/')]
    middle = [s.strip('/') for s in strings[1:-1]]
    return '/'.join(left + middle + right)
