from corehq.util.validation import is_url_or_host_banned
from django.test import TestCase


def inclusive_range(start, stop):
    return range(start, stop + 1)


class ValidationTestCase(TestCase):

    def testBannedHosts(self):
        self.assertTrue(is_url_or_host_banned('anything.commcarehq.org'))

        for i in inclusive_range(0, 255):
            for j in inclusive_range(0, 255):
                for k in inclusive_range(0, 255):
                    self.assertTrue(is_url_or_host_banned('10.%s.%s.%s' % (i, j, k)))

        for i in inclusive_range(16, 31):
            for j in inclusive_range(0, 255):
                for k in inclusive_range(0, 255):
                    self.assertTrue(is_url_or_host_banned('172.%s.%s.%s' % (i, j, k)))

        for i in inclusive_range(0, 255):
            for j in inclusive_range(0, 255):
                self.assertTrue(is_url_or_host_banned('192.168.%s.%s' % (i, j)))

        self.assertTrue(is_url_or_host_banned('127.0.0.1'))
        self.assertTrue(is_url_or_host_banned('localhost'))
        self.assertFalse(is_url_or_host_banned('dimagi.com'))
