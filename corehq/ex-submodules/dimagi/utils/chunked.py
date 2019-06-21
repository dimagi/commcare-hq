
from __future__ import absolute_import
from __future__ import unicode_literals
from itertools import islice


def chunked(it, n, collection=tuple):
    """
    >>> for nums in chunked(range(10), 4):
    ...    print(nums)
    ...
    (0, 1, 2, 3)
    (4, 5, 6, 7)
    (8, 9)
    >>> for nums in chunked(range(10), 4, list):
    ...    print(nums)
    ...
    [0, 1, 2, 3]
    [4, 5, 6, 7]
    [8, 9]
    """
    itr = iter(it)
    while True:
        items = take(n, itr, collection)
        if not items:
            break
        yield items


def take(n, iterable, collection=list):
    # https://docs.python.org/2/library/itertools.html#recipes
    return collection(islice(iterable, n))
