
def chunked(it, n):
    """
    >>> for nums in chunked(range(10), 4):
    ...    print nums
    (0, 1, 2, 3)
    (4, 5, 6, 7)
    (8, 9)
    """
    it = iter(it)
    while True:
        buffer = []
        try:
            for i in xrange(n):
                buffer.append(it.next())
            yield tuple(buffer)
        except StopIteration:
            if buffer:
                yield tuple(buffer)
            break
