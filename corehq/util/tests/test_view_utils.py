from unittest.mock import patch

import pytest
from django.test import RequestFactory, SimpleTestCase

from corehq.util.view_utils import get_safe_redirect_url, json_error


@json_error
def my_view(request, err):
    raise err


class NotifyExceptionTest(SimpleTestCase):

    def test_notify_exception_utf8(self):
        err = ValueError('βªđ ṿåƚŭę'.encode('utf-8'))
        with patch('corehq.util.view_utils.notify_exception') as notify_exception_patch:
            my_view('foo', err)
            notify_exception_patch.assert_called_with(
                'foo',
                "JSON exception response: ValueError: "
                "b'\\xce\\xb2\\xc2\\xaa\\xc4\\x91 \\xe1\\xb9\\xbf\\xc3\\xa5\\xc6\\x9a\\xc5\\xad\\xc4\\x99'"
            )


    def test_notify_exception_unicode(self):
        err = ValueError('βªđ ṿåƚŭę')
        with patch('corehq.util.view_utils.notify_exception') as notify_exception_patch:
            my_view('foo', err)
            notify_exception_patch.assert_called_with(
                'foo',
                'JSON exception response: ValueError: βªđ ṿåƚŭę',
            )


@pytest.mark.parametrize('url', [
    '/a/test-domain/',
    '/a/test-domain/reports/?q=1#frag',
    'relative/path/',
    'http://testserver/a/test-domain/',
])
def test_get_safe_redirect_url_accepts_same_site(url):
    request = RequestFactory().get('/')
    assert get_safe_redirect_url(request, url, '/default/') == url


@pytest.mark.parametrize('url', [
    None,
    '',
    'https://example.com/',
    'http://example.com/a/test-domain/',
    '//example.com/',
    '///example.com/',
    'https:///example.com/',
    'http:\\\\example.com/',
    '/\\example.com/',
    '\\\\example.com/',
    '\\/example.com/',
    ' //example.com/',
    '\t//example.com/',
    'javascript:alert(1)',
    'JavaScript:alert(1)',
    'data:text/html,<script>alert(1)</script>',
    'ftp://testserver/',
    'https://testserver.example.com/',
    'https://example.com@testserver.evil/',
])
def test_get_safe_redirect_url_rejects_other_sites(url):
    request = RequestFactory().get('/')
    assert get_safe_redirect_url(request, url, '/default/') == '/default/'


def test_get_safe_redirect_url_requires_https_on_secure_request():
    request = RequestFactory().get('/', secure=True)
    assert get_safe_redirect_url(request, 'http://testserver/x/', None) is None
    assert get_safe_redirect_url(request, 'https://testserver/x/', None) == 'https://testserver/x/'


def test_get_safe_redirect_url_uses_request_host():
    request = RequestFactory().get('/', HTTP_HOST='www.commcarehq.org')
    assert get_safe_redirect_url(request, 'http://www.commcarehq.org/x/', None) == 'http://www.commcarehq.org/x/'
    assert get_safe_redirect_url(request, 'http://testserver/x/', None) is None
