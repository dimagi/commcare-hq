from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from corehq.apps.domain.auth import HQApiKeyAuthentication
from corehq.apps.domain.decorators import api_auth
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import HQApiKey, WebUser

USERNAME = "joel@lastofus.com"
API_KEY = "123abc"


def has_credentials(request, allow_creds_in_data=True):
    actual = HQApiKeyAuthentication(allow_creds_in_data=allow_creds_in_data).extract_credentials(request)
    return actual == (USERNAME, API_KEY)


def test_no_auth():
    request = RequestFactory().get('/myapi/')
    assert not has_credentials(request)
    assert not has_credentials(request, allow_creds_in_data=False)


def test_credentials_in_META():
    request = RequestFactory().get('/myapi/')
    request.META['HTTP_AUTHORIZATION'] = f"ApiKey {USERNAME}:{API_KEY}"
    assert has_credentials(request)
    assert has_credentials(request, allow_creds_in_data=False)


def test_credentials_in_GET():
    request = RequestFactory().get(f'/myapi/?username={USERNAME}&api_key={API_KEY}')
    assert has_credentials(request)
    assert not has_credentials(request, allow_creds_in_data=False)


def test_credentials_in_POST():
    request = RequestFactory().post('/myapi/', {'username': USERNAME, 'api_key': API_KEY})
    assert has_credentials(request)
    assert not has_credentials(request, allow_creds_in_data=False)


class AuthenticationTestBase(TestCase):
    domain = 'api-key-test'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        domain_obj = create_domain(name=cls.domain)
        cls.addClassCleanup(domain_obj.delete)
        cls.user = WebUser.create(cls.domain, USERNAME, 'password', None, None)
        cls.api_key = HQApiKey.objects.create(user=cls.user.get_django_user()).plaintext_key

    def call_api(self, request, allow_creds_in_data):

        @api_auth(allow_creds_in_data=allow_creds_in_data)
        def api_view(request, domain):
            return HttpResponse()

        request.user = AnonymousUser()  # middleware normally does this
        return api_view(request, self.domain)

    def test_credentials_in_META(self):
        request = self.factory.get('/myapi/')
        request.META['HTTP_AUTHORIZATION'] = f"ApiKey {USERNAME}:{self.api_key}"

        res = self.call_api(request, allow_creds_in_data=True)
        self.assertEqual(res.status_code, 200)

        res = self.call_api(request, allow_creds_in_data=False)
        self.assertEqual(res.status_code, 200)

    def test_credentials_in_data(self):
        request = self.factory.get(f'/myapi/?username={USERNAME}&api_key={self.api_key}')

        res = self.call_api(request, allow_creds_in_data=True)
        self.assertEqual(res.status_code, 200)

        res = self.call_api(request, allow_creds_in_data=False)
        self.assertEqual(res.status_code, 401)
