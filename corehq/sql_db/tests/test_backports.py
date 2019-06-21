from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import doctest
import functools
import random
from collections import Counter

from corehq.sql_db import backports
from six.moves import range


def seed_random(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        random.seed(42)
        func(*args, **kwargs)
        random.seed()
    return wrapper


@seed_random
def test_weighted_choice():
    """
    Check results are roughly in the proportion we would expect.
    """
    population = ['one_half', 'one_third', 'one_sixth']
    weights = [3, 2, 1]
    results = [backports.choices(population, weights)[0] for __ in range(100)]
    counter = Counter(results)
    count_by_choice = dict(counter.most_common())
    assert count_by_choice['one_half'] == 50
    assert count_by_choice['one_third'] == 34
    assert count_by_choice['one_sixth'] == 16


@seed_random
def test_low_weight():
    """
    Check that choices with low weight aren't dropped
    """
    population = ['always', 'almost_never']
    weights = [999, 1]
    result_set = {backports.choices(population, weights)[0] for __ in range(1000)}
    assert 'always' in result_set
    assert 'almost_never' in result_set


def test_doctests():
    results = doctest.testmod(backports)
    assert results.failed == 0
