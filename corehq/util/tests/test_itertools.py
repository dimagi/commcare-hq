from __future__ import absolute_import, unicode_literals

from itertools import chain

from ..itertools import merge


def check_result(a, b, reverse, result):
    actual = list(merge(chain(a), chain(b), reverse=reverse))
    assert actual == result, "{} != {}".format(actual, result)


def test_merge():
    for a, b, result in [
            ([0, 1, 2], [3, 4, 5], list(range(6))),
            ([3, 4, 5], [0, 1, 2], list(range(6))),
            ([0, 2, 5], [1, 3, 4], list(range(6))),
            ([], [0, 3, 5], [0, 3, 5]),
            ([0, 3, 5], [], [0, 3, 5]),
            ([], [], []),
    ]:
        yield check_result, a, b, False, result


def test_merge_reversed():
    for a, b, result in [
        ([], [], []),
        ([4, 3, 1], [2, 0], [4, 3, 2, 1, 0]),
    ]:
        yield check_result, a, b, True, result
