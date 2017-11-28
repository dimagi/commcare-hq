
from __future__ import absolute_import
from six.moves import range
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
            for i in range(n):
                buffer.append(next(it))
            yield tuple(buffer)
        except StopIteration:
            if buffer:
                yield tuple(buffer)
            break
