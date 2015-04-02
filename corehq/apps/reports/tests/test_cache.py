import uuid
from django.http import HttpRequest
from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.reports.cache import request_cache
from corehq.apps.users.models import WebUser


class MockReport(object):
    is_cacheable = False

    def __init__(self, request, is_cacheable=True):
        self.request = request
        self.is_cacheable = is_cacheable

    @request_cache()
    def v1(self):
        return uuid.uuid4().hex

    @request_cache()
    def v2(self):
        return uuid.uuid4().hex


BLANK = '__blank__'
def _make_request(path=BLANK, domain=BLANK, user=BLANK):
    request = HttpRequest()
    if domain != BLANK:
        request.domain = domain
    if path != BLANK:
        request.path = path
    if user != BLANK:
        request.couch_user = user
    return request

class ReportCacheTest(TestCase):
    # note: this is pretty tightly coupled with the internals of the cache
    # but this is probably ok since that's what it's designed to test

    domain = 'cache-test'

    def setUp(self):
        create_domain(self.domain)
        self.web_user1 = WebUser.create(self.domain, 'w1', 'secret')
        self.web_user2 = WebUser.create(self.domain, 'w2', 'secret')

    def tearDown(self):
        self.web_user1.delete()
        self.web_user2.delete()

    def testBasicFunctionality(self):
        report = MockReport(_make_request('/a/{domain}/reports/foobar'.format(domain=self.domain),
                                          self.domain, self.web_user1))
        v1 = report.v1()
        #self.assertEqual(v1, report.v1())
        v2 = report.v2()
        self.assertEqual(v2, report.v2())
        self.assertNotEqual(v1, v2)
        copy = MockReport(_make_request('/a/{domain}/reports/foobar'.format(domain=self.domain),
                                        self.domain, self.web_user1))
        self.assertEqual(v1, copy.v1())
        self.assertEqual(v2, copy.v2())

    def testNonCacheable(self):
        report = MockReport(_make_request('/a/{domain}/reports/foobar'.format(domain=self.domain),
                                          self.domain, self.web_user1),
                            is_cacheable=False)
        v1 = report.v1()
        self.assertNotEqual(v1, report.v1())
        self.assertNotEqual(report.v1(), report.v1())

    def testPathSpecific(self):
        report = MockReport(_make_request('/a/{domain}/reports/foobar'.format(domain=self.domain),
                                          self.domain, self.web_user1))
        v1 = report.v1()
        v2 = report.v1()
        alternate_paths = [
            '/reports/barbar',
            '/reports/foobars',
            '/reports/foobar/baz',
            '/reports/foobar?bip=bop',
        ]
        for path in alternate_paths:
            full_path = '/a/{domain}{path}'.format(domain=self.domain, path=path)
            alternate = MockReport(_make_request(full_path, self.domain, self.web_user1))
            alt_v1 = alternate.v1()
            self.assertEqual(alt_v1, alternate.v1())
            alt_v2 = alternate.v2()
            self.assertEqual(alt_v2, alternate.v2())
            self.assertNotEqual(alt_v1, v1)
            self.assertNotEqual(alt_v2, v2)

    def testDomainSpecific(self):
        path = '/a/{domain}/reports/foobar'.format(domain=self.domain)
        report = MockReport(_make_request(path, self.domain, self.web_user1))
        v1 = report.v1()
        v2 = report.v1()
        alternate_domains = [
            'cache',
            'cachetest',
            'cache-testy',
            None,
            BLANK,
        ]
        for dom in alternate_domains:
            alternate = MockReport(_make_request(path, dom, self.web_user1))
            alt_v1 = alternate.v1()
            # since this is invalid, this shouldn't even be caching itself
            self.assertNotEqual(alt_v1, alternate.v1())
            alt_v2 = alternate.v2()
            self.assertNotEqual(alt_v2, alternate.v2())
            self.assertNotEqual(alt_v1, v1)
            self.assertNotEqual(alt_v2, v2)

    def testUserSpecific(self):
        path = '/a/{domain}/reports/foobar'.format(domain=self.domain)
        report = MockReport(_make_request(path, self.domain, self.web_user1))
        v1 = report.v1()
        v2 = report.v1()

        alternate = MockReport(_make_request(path, self.domain, self.web_user2))
        alt_v1 = alternate.v1()
        self.assertEqual(alt_v1, alternate.v1())
        alt_v2 = alternate.v2()
        self.assertEqual(alt_v2, alternate.v2())
        self.assertNotEqual(alt_v1, v1)
        self.assertNotEqual(alt_v2, v2)


        # invalid users shouldn't even be caching themselves
        for invalid in ['not a user object', None, BLANK]:
            alternate = MockReport(_make_request(path, self.domain, invalid))
            alt_v1 = alternate.v1()
            # since this is invalid, this shouldn't even be caching itself
            self.assertNotEqual(alt_v1, alternate.v1())
            alt_v2 = alternate.v2()
            self.assertNotEqual(alt_v2, alternate.v2())
            self.assertNotEqual(alt_v1, v1)
            self.assertNotEqual(alt_v2, v2)
