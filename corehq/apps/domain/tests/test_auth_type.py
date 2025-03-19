from django.test import RequestFactory, SimpleTestCase

import requests

from no_exceptions.exceptions import Http400

from ..auth import determine_authtype_from_request


class TestDetermineAuthType(SimpleTestCase):

    @staticmethod
    def _mock_request(user_agent='', auth_header=''):
        class FakeRequest(object):

            def __init__(self, user_agent, auth_header):
                self.META = {
                    'HTTP_USER_AGENT': user_agent,
                    'HTTP_AUTHORIZATION': auth_header,
                }
                self.GET = self.POST = {}

        return FakeRequest(user_agent, auth_header)

    def test_digest_is_default(self):
        self.assertEqual('digest', determine_authtype_from_request(self._mock_request()))

    def test_override_default(self):
        self.assertEqual('digest', determine_authtype_from_request(self._mock_request()))

    def test_basic_header_overrides_default(self):
        self.assertEqual('basic',
                         determine_authtype_from_request(self._mock_request(auth_header='Basic whatever')))


class TestDetermineAuthTypeFromRequest(SimpleTestCase):
    """
    Similar approach to the above test case, but here we use python requests to
    set the headers
    """

    def get_django_request(self, auth=None, headers=None):
        def to_django_header(header_key):
            # python simple_server.WSGIRequestHandler does basically this:
            return 'HTTP_' + header_key.upper().replace('-', '_')

        req = (requests.Request(
            'GET',
            'https://example.com',
            auth=auth,
            headers=headers,
        ).prepare())

        return RequestFactory().generic(
            method=req.method,
            path=req.path_url,
            data=req.body,
            **{to_django_header(k): v for k, v in req.headers.items()}
        )

    def test_basic_auth(self):
        request = self.get_django_request(auth=requests.auth.HTTPBasicAuth('foo', 'bar'))
        self.assertEqual('basic', determine_authtype_from_request(request))

    def test_digest_auth(self):
        request = self.get_django_request(auth=requests.auth.HTTPDigestAuth('foo', 'bar'))
        self.assertEqual('digest', determine_authtype_from_request(request))

    def test_api_auth(self):
        # http://django-tastypie.readthedocs.io/en/latest/authentication.html#apikeyauthentication
        request = self.get_django_request(headers={
            'Authorization': 'ApiKey username:api_key'
        })
        self.assertEqual('api_key', determine_authtype_from_request(request))

    def test_api_auth_bad_format(self):
        request = self.get_django_request(headers={
            'Authorization': 'ApiKey See LastPass'
        })
        with self.assertRaises(Http400):
            determine_authtype_from_request(request)
