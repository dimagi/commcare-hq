from collections import namedtuple
from mock import patch

from requests.exceptions import Timeout, ConnectionError
from django.core.cache import cache
from django.test import SimpleTestCase

from corehq.apps.repeaters.models import simple_post_with_cached_timeout
from corehq.apps.repeaters.exceptions import RequestConnectionError

MockResponse = namedtuple('MockResponse', 'status_code reason')


class SimplePostCacheTest(SimpleTestCase):

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_simple_post_with_cached_timeout_success(self):
        with patch(
                'corehq.apps.repeaters.models.simple_post',
                side_effect=[MockResponse(status_code=200, reason='No reason')]) as mock_post:

            resp = simple_post_with_cached_timeout('abc', 'http://google.com')

            self.assertEqual(mock_post.call_count, 1)
            self.assertEqual(resp.status_code, 200)

    def test_simple_post_with_cached_timeout_error(self):
        """
        Ensures that when a post is made to the same URL that has timed out previous
        in the last hour, it will not make another post request
        """

        with patch('corehq.apps.repeaters.models.simple_post', side_effect=Timeout('Timeout!')) as mock_post:
            with self.assertRaises(RequestConnectionError):
                simple_post_with_cached_timeout('abc', 'http://google.com')

            self.assertEqual(mock_post.call_count, 1)

            with self.assertRaises(RequestConnectionError):
                simple_post_with_cached_timeout('abc', 'http://google.com')

            self.assertEqual(mock_post.call_count, 1)

    def test_simple_post_with_cached_timeout_bad_http_response(self):
        """
        Ensure that when an http response returns outside 200 or 300 response it caches
        """
        with patch(
                'corehq.apps.repeaters.models.simple_post',
                side_effect=[MockResponse(status_code=400, reason='Ugly')]) as mock_post:

            simple_post_with_cached_timeout('abc', 'http://google.com')

            self.assertEqual(mock_post.call_count, 1)

            with self.assertRaises(RequestConnectionError):
                simple_post_with_cached_timeout('abc', 'http://google.com')

            self.assertEqual(mock_post.call_count, 1)

    def test_bust_cache_new_url(self):
        """
        Ensure that the cache is busted when the URL changes
        """
        with patch(
                'corehq.apps.repeaters.models.simple_post',
                side_effect=ConnectionError('Timeout!')) as mock_post:
            with self.assertRaises(RequestConnectionError):
                simple_post_with_cached_timeout('abc', 'http://google.com')

            self.assertEqual(mock_post.call_count, 1)

            with self.assertRaises(RequestConnectionError):
                simple_post_with_cached_timeout('abc', 'http://different.com')

            self.assertEqual(mock_post.call_count, 2)

    def test_force_send(self):
        with patch(
                'corehq.apps.repeaters.models.simple_post',
                side_effect=ConnectionError('Timeout!')) as mock_post:
            with self.assertRaises(RequestConnectionError):
                simple_post_with_cached_timeout('abc', 'http://google.com')

            self.assertEqual(mock_post.call_count, 1)

            with self.assertRaises(RequestConnectionError):
                simple_post_with_cached_timeout('abc', 'http://google.com', force_send=True)

            self.assertEqual(mock_post.call_count, 2)
