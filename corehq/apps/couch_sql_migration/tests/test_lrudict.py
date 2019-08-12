from __future__ import absolute_import
from __future__ import unicode_literals

from nose.plugins.skip import SkipTest
from testil import assert_raises, eq

from ..lrudict import LRUDict


def test_getitem():
    lru = LRUDict(3)
    for x in range(4):
        lru[x] = x * 2
        eq(lru[0], 0, "x: %s" % x)
    with assert_raises(KeyError):
        lru[-1]
    assert_items_equal(lru, [(2, 4), (3, 6), (0, 0)])


def test_get():
    lru = LRUDict(3)
    for x in range(4):
        lru[x] = x * 2
        eq(lru.get(0), 0, "x: %s" % x)
    eq(lru.get(-1, -2), -2)
    assert_items_equal(lru, [(2, 4), (3, 6), (0, 0)])


def test_setitem():
    lru = LRUDict(3)
    for x in range(4):
        lru[x] = x * 2
    lru[2] = 5
    assert_items_equal(lru, [(1, 2), (3, 6), (2, 5)])


def test_setdefault():
    lru = LRUDict(3)
    for x in range(4):
        lru.setdefault(x, x * 2)
        lru.setdefault(0, 1000)
    assert_items_equal(lru, [(2, 4), (3, 6), (0, 0)])


def test_update():
    lru = LRUDict(3)
    lru.update((x, x * 2) for x in range(4))
    assert_items_equal(lru, [(1, 2), (2, 4), (3, 6)])


def test_update_with_duplicate_keys():
    raise SkipTest("broken edge case")
    lru = LRUDict(3)
    lru.update((x, x) for x in [0, 1, 2, 3, 0])
    assert_items_equal(lru, [(2, 4), (3, 6), (0, 0)])


def assert_items_equal(lru, items):
    keys = [k for k, v in items]
    values = [v for k, v in items]
    eq(list(lru.items()), items)
    eq(list(lru), keys)
    eq(list(lru.keys()), keys)
    eq(list(lru.values()), values)
    if hasattr(lru, "iterkeys"):
        eq(list(lru.iterkeys()), keys)
        eq(list(lru.itervalues()), values)
