import base64
import json

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from corehq.apps.domain.auth import HQApiKeyAuthentication
from corehq.apps.domain.decorators import SSO_AUTH_FAIL_RESPONSE, api_auth
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.sso.models import AuthenticatedEmailDomain, LoginEnforcementType
from corehq.apps.sso.tests import generator as sso_generator
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

    def call_api(self, request, allow_creds_in_data=False):

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

    def test_credentials_with_basic_auth(self):
        request = self.factory.get('/myapi/')
        encoded_creds = base64.b64encode(f"{USERNAME}:{self.api_key}".encode('utf-8')).decode('utf-8')
        request.META['HTTP_AUTHORIZATION'] = f"basic {encoded_creds}"

        res = self.call_api(request)
        self.assertEqual(res.status_code, 200)


class SSOApiAuthenticationTest(AuthenticationTestBase):
    sso_username = "ellie@ssocompany.com"
    domain = 'sso-api-key-test'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = sso_generator.get_billing_account_for_idp()

        cls.idp = sso_generator.create_idp('sso-api-test', cls.account)
        cls.idp.is_active = True
        cls.idp.login_enforcement_type = LoginEnforcementType.GLOBAL
        cls.idp.save()
        AuthenticatedEmailDomain.objects.create(
            email_domain='ssocompany.com',
            identity_provider=cls.idp,
        )

        cls.sso_user = WebUser.create(
            cls.domain, cls.sso_username, 'password', None, None
        )
        cls.sso_api_key = HQApiKey.objects.create(
            user=cls.sso_user.get_django_user()
        ).plaintext_key

    def test_sso_user_with_api_key_auth_succeeds(self):
        request = self.factory.get('/myapi/')
        request.META['HTTP_AUTHORIZATION'] = f"ApiKey {self.sso_username}:{self.sso_api_key}"
        res = self.call_api(request)
        assert res.status_code == 200

    def test_sso_user_with_basic_auth_is_rejected(self):
        request = self.factory.get('/myapi/')
        encoded = base64.b64encode(
            f"{self.sso_username}:password".encode('utf-8')
        ).decode('utf-8')
        request.META['HTTP_AUTHORIZATION'] = f"basic {encoded}"
        res = self.call_api(request)
        assert res.status_code == 401
        assert json.loads(res.content) == SSO_AUTH_FAIL_RESPONSE

    def test_non_sso_user_with_basic_auth_succeeds(self):
        request = self.factory.get('/myapi/')
        encoded = base64.b64encode(
            f"{USERNAME}:password".encode('utf-8')
        ).decode('utf-8')
        request.META['HTTP_AUTHORIZATION'] = f"basic {encoded}"
        res = self.call_api(request)
        assert res.status_code == 200
