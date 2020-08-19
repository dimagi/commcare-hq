from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, RequestFactory

from corehq.apps.api.resources.auth import LoginAuthentication
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser, HQApiKey


class LoginAuthenticationTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(LoginAuthenticationTest, cls).setUpClass()
        cls.factory = RequestFactory()
        cls.domain = Domain.get_or_create_with_name('api-test', is_active=True)
        cls.username = 'alice@example.com'
        cls.password = '***'
        cls.user = WebUser.create(cls.domain.name, cls.username, cls.password, None, None)
        cls.api_key, _ = HQApiKey.objects.get_or_create(user=WebUser.get_django_user(cls.user))

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super().tearDownClass()

    def _get_request_with_api_key(self):
        return self._get_request(HTTP_AUTHORIZATION=f'ApiKey {self.username}:{self.api_key.key}')

    def _get_request(self, **extras):
        request = self.factory.get('', **extras)
        request.user = AnonymousUser()  # this is required for HQ's permission classes to resolve
        return request

    def assertAuthenticationSuccess(self, auth_instance, request):
        self.assertTrue(auth_instance.is_authenticated(request))

    def assertAuthenticationFail(self, auth_instance, request):
        self.assertFalse(auth_instance.is_authenticated(request))

    def test_login_no_auth(self):
        self.assertAuthenticationFail(LoginAuthentication(), self._get_request())

    def test_login_with_auth(self):
        self.assertAuthenticationSuccess(LoginAuthentication(), self._get_request_with_api_key())
