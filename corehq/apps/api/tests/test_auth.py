from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import TestCase, RequestFactory

from corehq.apps.api.resources.auth import LoginAuthentication, LoginAndDomainAuthentication, \
    RequirePermissionAuthentication
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser, HQApiKey, Permissions, UserRole


class AuthenticationTestBase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.domain = 'api-test'
        cls.project = Domain.get_or_create_with_name(cls.domain, is_active=True)
        cls.username = 'alice@example.com'
        cls.password = '***'
        cls.user = WebUser.create(cls.domain, cls.username, cls.password, None, None)
        cls.api_key, _ = HQApiKey.objects.get_or_create(user=WebUser.get_django_user(cls.user))

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super().tearDownClass()

    def _get_request_with_api_key(self, domain=None):
        return self._get_request(domain,
                                 HTTP_AUTHORIZATION=self._contruct_api_auth_header(self.username, self.api_key))

    def _contruct_api_auth_header(self, username, api_key):
        return f'ApiKey {username}:{api_key.key}'

    def _get_request(self, domain=None, **extras):
        path = self._get_domain_path() if domain else ''
        request = self.factory.get(path, **extras)
        request.user = AnonymousUser()  # this is required for HQ's permission classes to resolve
        request.domain = domain  # as is this for any domain-specific request
        return request

    def _get_domain_path(self):
        return f'/a/{self.domain}/'

    def assertAuthenticationSuccess(self, auth_instance, request):
        # we can't use assertTrue, because auth failures can return "truthy" HttpResponse objects
        self.assertEqual(True, auth_instance.is_authenticated(request))

    def assertAuthenticationFail(self, auth_instance, request):
        result = auth_instance.is_authenticated(request)
        # currently auth classes return a 401/403 response in some scenarios
        # this should likely be changed to always return False
        # more discussion here: https://github.com/dimagi/commcare-hq/pull/28201#discussion_r461082885
        if isinstance(result, HttpResponse):
            self.assertIn(result.status_code, (401, 403))
        else:
            self.assertFalse(result)


class LoginAuthenticationTest(AuthenticationTestBase):

    def test_login_no_auth(self):
        self.assertAuthenticationFail(LoginAuthentication(), self._get_request())

    def test_login_with_auth(self):
        self.assertAuthenticationSuccess(LoginAuthentication(), self._get_request_with_api_key())


class LoginAndDomainAuthenticationTest(AuthenticationTestBase):

    def test_login_no_auth_no_domain(self):
        self.assertAuthenticationFail(LoginAndDomainAuthentication(), self._get_request())

    def test_login_no_auth_with_domain(self):
        self.assertAuthenticationFail(LoginAndDomainAuthentication(), self._get_request(domain=self.domain))

    def test_login_with_domain(self):
        self.assertAuthenticationSuccess(LoginAndDomainAuthentication(),
                                         self._get_request_with_api_key(domain=self.domain))

    def test_login_with_wrong_domain(self):
        project = Domain.get_or_create_with_name('api-test-fail', is_active=True)
        self.addCleanup(project.delete)
        self.assertAuthenticationFail(LoginAndDomainAuthentication(),
                                      self._get_request_with_api_key(domain=project.name))


class RequirePermissionAuthenticationTest(AuthenticationTestBase):
    require_edit_data = RequirePermissionAuthentication(Permissions.edit_data)

    def test_login_no_auth_no_domain(self):
        self.assertAuthenticationFail(self.require_edit_data, self._get_request())

    def test_login_no_auth_with_domain(self):
        self.assertAuthenticationFail(self.require_edit_data, self._get_request(domain=self.domain))

    def test_login_with_wrong_domain(self):
        project = Domain.get_or_create_with_name('api-test-fail', is_active=True)
        self.addCleanup(project.delete)
        self.assertAuthenticationFail(self.require_edit_data,
                                      self._get_request_with_api_key(domain=project.name))

    def test_login_with_domain_no_permissions(self):
        self.assertAuthenticationFail(self.require_edit_data,
                                      self._get_request_with_api_key(domain=self.domain))

    def test_login_with_domain_admin(self):
        user_with_permission = WebUser.create(self.domain, 'domain_admin', '***', None, None, is_admin=True)
        api_key_with_permissions, _ = HQApiKey.objects.get_or_create(
            user=WebUser.get_django_user(user_with_permission)
        )
        self.addCleanup(lambda: user_with_permission.delete(None))
        self.assertAuthenticationSuccess(self.require_edit_data,
                                         self._get_request(
                                             domain=self.domain,
                                             HTTP_AUTHORIZATION=self._contruct_api_auth_header(
                                                 user_with_permission.username,
                                                 api_key_with_permissions
                                             )
                                         ))

    def test_login_with_explicit_permission(self):
        role = UserRole.get_or_create_with_permissions(self.domain, Permissions(edit_data=True), 'edit-data')
        self.addCleanup(role.delete)
        user_with_permission = WebUser.create(self.domain, 'permission', '***', None, None, role_id=role.get_id)
        api_key_with_permissions, _ = HQApiKey.objects.get_or_create(
            user=WebUser.get_django_user(user_with_permission)
        )
        self.addCleanup(lambda: user_with_permission.delete(None))
        self.assertAuthenticationSuccess(self.require_edit_data,
                                         self._get_request(
                                             domain=self.domain,
                                             HTTP_AUTHORIZATION=self._contruct_api_auth_header(
                                                 user_with_permission.username,
                                                 api_key_with_permissions
                                             )
                                         ))

    def test_login_with_wrong_permission(self):
        role = UserRole.get_or_create_with_permissions(self.domain, Permissions(edit_data=False), 'edit-data')
        self.addCleanup(role.delete)
        user_with_permission = WebUser.create(self.domain, 'permission', '***', None, None, role_id=role.get_id)
        api_key_with_permissions, _ = HQApiKey.objects.get_or_create(
            user=WebUser.get_django_user(user_with_permission)
        )
        self.addCleanup(lambda: user_with_permission.delete(None))
        self.assertAuthenticationFail(self.require_edit_data,
                                      self._get_request(
                                          domain=self.domain,
                                          HTTP_AUTHORIZATION=self._contruct_api_auth_header(
                                              user_with_permission.username,
                                              api_key_with_permissions
                                          )
                                      ))
