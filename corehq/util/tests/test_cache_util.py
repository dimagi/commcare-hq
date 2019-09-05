from django.test import SimpleTestCase
from django.core.cache import cache
from corehq.util.cache_utils import ExponentialBackoff


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
