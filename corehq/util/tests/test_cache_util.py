from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from django.core.cache import cache
from corehq.util.cache_utils import ExponentialBackoff, ExponentialGrowth


class TestExponentialBackoff(SimpleTestCase):

    def tearDown(self):
        cache.clear()

    def test_backoff(self):
        key = 'new key'

        self.assertFalse(ExponentialBackoff.should_backoff(key))
        self.assertFalse(ExponentialBackoff.should_backoff(key))

        ExponentialBackoff.increment(key)  # first incr is 1
        self.assertFalse(ExponentialBackoff.should_backoff(key))

        ExponentialBackoff.increment(key)  # incr to 2
        self.assertFalse(ExponentialBackoff.should_backoff(key))

        ExponentialBackoff.increment(key)  # incr to 3
        self.assertTrue(ExponentialBackoff.should_backoff(key))

        ExponentialBackoff.increment(key)  # incr to 4
        self.assertFalse(ExponentialBackoff.should_backoff(key))

    def test_backoff_none(self):
        key = None
        ExponentialBackoff.increment(key)  # first incr is 1
        self.assertFalse(ExponentialBackoff.should_backoff(key))


class TestExponentialGrowth(SimpleTestCase):
    def setUp(self):
        self.key = "the.way.is.shut"

    def tearDown(self):
        ExponentialGrowth.invalidate(self.key)

    def test_grow(self):
        self.assertEqual(5, ExponentialGrowth.get_next_time(self.key))
        self.assertEqual(10, ExponentialGrowth.get_next_time(self.key))
        self.assertEqual(20, ExponentialGrowth.get_next_time(self.key))

    def test_base_time(self):
        self.assertEqual(3, ExponentialGrowth.get_next_time(self.key, 3))
        self.assertEqual(6, ExponentialGrowth.get_next_time(self.key, 3))
        self.assertEqual(12, ExponentialGrowth.get_next_time(self.key, 3))

    def test_max_time(self):
        self.assertEqual(20, ExponentialGrowth.get_next_time(self.key, 20))
        self.assertEqual(30, ExponentialGrowth.get_next_time(self.key, 20, 30))
