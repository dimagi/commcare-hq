from corehq.util.urlvalidate.test.mockipinfo import unresolvable_hostname
from corehq.util.urlvalidate.ip_resolver import CannotResolveHost
from random import sample

from corehq.util.validation import is_url_or_host_banned
from django.test import SimpleTestCase


def sample_range(start, stop):
    yield start
    num_samples = min(8, stop - start)
    for middle in sample(range(start + 1, stop), num_samples):
        yield middle
    yield stop


class ValidationTestCase(SimpleTestCase):

    def testBannedHosts(self):
        self.assertTrue(is_url_or_host_banned('anything.commcarehq.org'))

        for i in sample_range(0, 255):
            for j in sample_range(0, 255):
                for k in sample_range(0, 255):
                    self.assertTrue(is_url_or_host_banned('10.%s.%s.%s' % (i, j, k)))

        for i in sample_range(16, 31):
            for j in sample_range(0, 255):
                for k in sample_range(0, 255):
                    self.assertTrue(is_url_or_host_banned('172.%s.%s.%s' % (i, j, k)))

        for i in sample_range(0, 255):
            for j in sample_range(0, 255):
                self.assertTrue(is_url_or_host_banned('192.168.%s.%s' % (i, j)))

        self.assertTrue(is_url_or_host_banned('127.0.0.1'))
        self.assertTrue(is_url_or_host_banned('localhost'))
        self.assertFalse(is_url_or_host_banned('dimagi.com'))

    def test_rejects_localhost(self):
        self.assertTrue(is_url_or_host_banned('http://localhost'))

    def test_rejects_ipv6_localhost(self):
        self.assertTrue(is_url_or_host_banned('http://[::1]'))

    def test_accepts_host_without_scheme(self):
        self.assertFalse(is_url_or_host_banned('google.com'))

    def test_rejects_localhost_without_schema(self):
        self.assertTrue(is_url_or_host_banned('localhost'))

    def test_unresolvable_address_raises_error(self):
        with unresolvable_hostname('not.a.real.address'):
            with self.assertRaises(CannotResolveHost):
                is_url_or_host_banned('http://not.a.real.address')
