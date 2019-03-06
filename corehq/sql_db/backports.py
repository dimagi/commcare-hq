from __future__ import absolute_import
from __future__ import unicode_literals

import operator
import random
from bisect import bisect
from itertools import repeat


# Backported from Python 3.2 itertools.accumulate
# cf. https://docs.python.org/3/library/itertools.html#itertools.accumulate
def accumulate(iterable, func=operator.add):
    """
    Return running totals

    >>> list(accumulate([1, 2, 3, 4, 5]))
    [1, 3, 6, 10, 15]
    >>> list(accumulate([1,2,3,4,5], operator.mul))
    [1, 2, 6, 24, 120]

    """
    it = iter(iterable)
    try:
        total = next(it)
    except StopIteration:
        return
    yield total
    for element in it:
        total = func(total, element)
        yield total


# Backported from Python 3.6 random.choices
# cf. https://github.com/python/cpython/blob/3.6/Lib/random.py#L343-L365
def choices(population, weights=None, **kwargs):
    """
    Return a k sized list of population elements chosen with replacement.
    If the relative weights or cumulative weights are not specified,
    the selections are made with equal probability.
    """
    cum_weights = kwargs.pop('cum_weights', None)
    k = kwargs.pop('k', 1)

    random_ = random.random
    n = len(population)
    if cum_weights is None:
        if weights is None:
            _int = int
            n += 0.0    # convert to float for a small speed improvement
            return [population[_int(random_() * n)]
                    for __ in repeat(None, k)]
        cum_weights = list(accumulate(weights))
    elif weights is not None:
        raise TypeError('Cannot specify both weights and cumulative weights')
    if len(cum_weights) != n:
        raise ValueError('The number of weights does not match the population')
    total = cum_weights[-1] + 0.0   # convert to float
    hi = n - 1
    return [population[bisect(cum_weights, random_() * total, 0, hi)]
            for __ in repeat(None, k)]
