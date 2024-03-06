import base64
from datetime import datetime, timedelta

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import TestCase, RequestFactory

from corehq.apps.api.resources.auth import LoginAuthentication, LoginAndDomainAuthentication, \
    RequirePermissionAuthentication
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser, HQApiKey, HqPermissions, UserRole
from corehq.util.test_utils import softer_assert


class AuthenticationTestBase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.domain = 'api-test'
        cls.project = Domain.get_or_create_with_name(cls.domain, is_active=True)
        cls.username = 'alice@example.com'
        cls.password = '***'
        cls.api_user_role = UserRole.create(
            cls.domain, 'api-user', permissions=HqPermissions(access_api=True)
        )
        cls.user = WebUser.create(cls.domain, cls.username, cls.password, None, None,
                                  role_id=cls.api_user_role.get_id)
        cls.api_key, _ = HQApiKey.objects.get_or_create(user=WebUser.get_django_user(cls.user))
        cls.domain_api_key, _ = HQApiKey.objects.get_or_create(user=WebUser.get_django_user(cls.user),
                                                               name='domain-scoped',
                                                               domain=cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super().tearDownClass()

    def _get_request_with_api_key(self, domain=None):
        return self._get_request(domain,
                                 HTTP_AUTHORIZATION=self._construct_api_auth_header(self.username, self.api_key))

    def _get_request_with_basic_auth(self, domain=None):
        return self._get_request(
            domain,
            HTTP_AUTHORIZATION=self._construct_basic_auth_header(self.username, self.password)
        )

    def _construct_api_auth_header(self, username, api_key):
        return f'ApiKey {username}:{api_key.key}'

    def _construct_basic_auth_header(self, username, password):
        # https://stackoverflow.com/q/5495452/8207
        encoded_auth = base64.b64encode(bytes(f'{username}:{password}', 'utf8')).decode('utf8')
        return f'Basic {encoded_auth}'

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

    def test_login_with_api_key_auth(self):
        self.assertAuthenticationSuccess(LoginAuthentication(), self._get_request_with_api_key())
        self.api_key.refresh_from_db()
        self.assertIsNotNone(self.api_key.last_used)

    def test_auth_type_basic(self):
        self.assertAuthenticationSuccess(LoginAuthentication(), self._get_request_with_basic_auth())

    def test_login_with_inactive_api_key(self):
        def reactivate_key():
            self.api_key.is_active = True
            self.api_key.save()

        self.api_key.is_active = False
        self.api_key.last_used = None
        self.api_key.save()
        self.addCleanup(reactivate_key)
        self.assertAuthenticationFail(LoginAuthentication(), self._get_request_with_api_key())
        self.api_key.refresh_from_db()
        self.assertIsNone(self.api_key.last_used)

    def test_login_with_expired_api_key(self):
        def reactivate_key():
            self.api_key.expiration_date = None
            self.api_key.save()

        self.api_key.expiration_date = datetime.today() - timedelta(days=2)
        self.api_key.last_used = None
        self.api_key.save()
        self.addCleanup(reactivate_key)
        self.assertAuthenticationFail(LoginAuthentication(), self._get_request_with_api_key())
        self.api_key.refresh_from_db()
        self.assertIsNone(self.api_key.last_used)

    def test_login_with_not_yet_expired_api_key(self):
        def reactivate_key():
            self.api_key.expiration_date = None
            self.api_key.save()

        self.api_key.expiration_date = datetime.today() + timedelta(days=2)
        self.api_key.last_used = None
        self.api_key.save()
        self.addCleanup(reactivate_key)
        self.assertAuthenticationSuccess(LoginAuthentication(), self._get_request_with_api_key())
        self.api_key.refresh_from_db()
        self.assertIsNotNone(self.api_key.last_used)

    def test_login_with_deactivated_user(self):
        def reactivate_user():
            self.user.is_active = True
            self.user.save()
        self.user.is_active = False
        self.user.save()
        self.addCleanup(reactivate_user)
        self.assertAuthenticationFail(LoginAuthentication(), self._get_request_with_api_key())
        self.api_key.refresh_from_db()
        self.assertIsNone(self.api_key.last_used)


class LoginAndDomainAuthenticationTest(AuthenticationTestBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain2 = 'api-test-other'
        cls.project2 = Domain.get_or_create_with_name(cls.domain2, is_active=True)
        cls.user.add_domain_membership(cls.domain2, is_admin=True)
        cls.user.save()

    @classmethod
    def tearDownClass(cls):
        cls.project2.delete()
        super().tearDownClass()

    def test_login_no_auth_no_domain(self):
        self.assertAuthenticationFail(LoginAndDomainAuthentication(), self._get_request())

    def test_login_no_auth_with_domain(self):
        self.assertAuthenticationFail(LoginAndDomainAuthentication(), self._get_request(domain=self.domain))

    def test_login_with_domain(self):
        self.assertAuthenticationSuccess(LoginAndDomainAuthentication(),
                                         self._get_request_with_api_key(domain=self.domain))
        self.assertAuthenticationSuccess(LoginAndDomainAuthentication(),
                                         self._get_request_with_api_key(domain=self.domain2))

    def test_login_with_domain_key(self):
        self.assertAuthenticationSuccess(
            LoginAndDomainAuthentication(),
            self._get_request(
                self.domain,
                HTTP_AUTHORIZATION=self._construct_api_auth_header(
                    self.username,
                    self.domain_api_key
                )
            )
        )

    def test_login_with_domain_key_wrong(self):
        self.assertAuthenticationFail(
            LoginAndDomainAuthentication(),
            self._get_request(
                self.domain2,
                HTTP_AUTHORIZATION=self._construct_api_auth_header(
                    self.username,
                    self.domain_api_key
                )
            )
        )

    def test_login_with_wrong_domain(self):
        project = Domain.get_or_create_with_name('api-test-fail', is_active=True)
        self.addCleanup(project.delete)
        self.assertAuthenticationFail(LoginAndDomainAuthentication(),
                                      self._get_request_with_api_key(domain=project.name))

    @softer_assert()  # prevent "None is invalid domain" asserts
    def test_auth_type_basic_no_domain(self):
        self.assertAuthenticationFail(LoginAndDomainAuthentication(),
                                      self._get_request_with_basic_auth())

    def test_auth_type_basic_with_domain(self):
        self.assertAuthenticationSuccess(LoginAndDomainAuthentication(),
                                         self._get_request_with_basic_auth(domain=self.domain))


class RequirePermissionAuthenticationTest(AuthenticationTestBase):
    require_edit_data = RequirePermissionAuthentication(HqPermissions.edit_data)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role_with_permission = UserRole.create(
            cls.domain, 'edit-data', permissions=HqPermissions(edit_data=True, access_api=True)
        )
        cls.role_without_permission = UserRole.create(
            cls.domain, 'no-edit-data', permissions=HqPermissions(edit_data=False, access_api=True)
        )
        cls.role_with_permission_but_no_api_access = UserRole.create(
            cls.domain, 'no-api-access', permissions=HqPermissions(edit_data=True, access_api=False)
        )
        cls.domain_admin = WebUser.create(cls.domain, 'domain_admin', cls.password, None, None, is_admin=True)
        cls.user_with_permission = WebUser.create(cls.domain, 'permission', cls.password, None, None,
                                                  role_id=cls.role_with_permission.get_id)
        cls.user_without_permission = WebUser.create(cls.domain, 'no-permission', cls.password, None, None,
                                                     role_id=cls.role_without_permission.get_id)
        cls.user_with_permission_but_no_api_access = WebUser.create(
            cls.domain, 'no-api-access', cls.password, None, None,
            role_id=cls.role_with_permission_but_no_api_access.get_id,
        )

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

    def test_login_with_domain_admin_default(self):
        api_key_with_default_permissions, _ = HQApiKey.objects.get_or_create(
            user=WebUser.get_django_user(self.domain_admin),
            name='default',
        )
        self.assertAuthenticationSuccess(self.require_edit_data,
                                         self._get_request(
                                             domain=self.domain,
                                             HTTP_AUTHORIZATION=self._construct_api_auth_header(
                                                 self.domain_admin.username,
                                                 api_key_with_default_permissions
                                             )
                                         ))

    def test_domain_admin_with_explicit_roles(self):
        api_key_with_explicit_permissions, _ = HQApiKey.objects.get_or_create(
            user=WebUser.get_django_user(self.domain_admin),
            name='explicit_with_permission',
            role_id=self.role_with_permission.get_id,
        )
        api_key_without_explicit_permissions, _ = HQApiKey.objects.get_or_create(
            user=WebUser.get_django_user(self.domain_admin),
            name='explicit_without_permission',
            role_id=self.role_without_permission.get_id,
        )
        self.assertAuthenticationSuccess(self.require_edit_data,
                                         self._get_request(
                                             domain=self.domain,
                                             HTTP_AUTHORIZATION=self._construct_api_auth_header(
                                                 self.domain_admin.username,
                                                 api_key_with_explicit_permissions
                                             )
                                         ))
        self.assertAuthenticationFail(self.require_edit_data,
                                      self._get_request(
                                          domain=self.domain,
                                          HTTP_AUTHORIZATION=self._construct_api_auth_header(
                                              self.domain_admin.username,
                                              api_key_without_explicit_permissions
                                          )
                                      ))

    def test_login_with_explicit_permission_default(self):
        api_key_with_permissions, _ = HQApiKey.objects.get_or_create(
            user=WebUser.get_django_user(self.user_with_permission)
        )
        self.assertAuthenticationSuccess(self.require_edit_data,
                                         self._get_request(
                                             domain=self.domain,
                                             HTTP_AUTHORIZATION=self._construct_api_auth_header(
                                                 self.user_with_permission.username,
                                                 api_key_with_permissions
                                             )
                                         ))

    def test_login_with_explicit_permission_and_roles(self):
        api_key_with_explicit_permissions, _ = HQApiKey.objects.get_or_create(
            user=WebUser.get_django_user(self.user_with_permission),
            name='explicit_with_permission',
            role_id=self.role_with_permission.get_id,
        )
        api_key_without_explicit_permissions, _ = HQApiKey.objects.get_or_create(
            user=WebUser.get_django_user(self.user_with_permission),
            name='explicit_without_permission',
            role_id=self.role_without_permission.get_id,
        )
        self.assertAuthenticationSuccess(self.require_edit_data,
                                         self._get_request(
                                             domain=self.domain,
                                             HTTP_AUTHORIZATION=self._construct_api_auth_header(
                                                 self.user_with_permission.username,
                                                 api_key_with_explicit_permissions
                                             )
                                         ))
        self.assertAuthenticationFail(self.require_edit_data,
                                      self._get_request(
                                          domain=self.domain,
                                          HTTP_AUTHORIZATION=self._construct_api_auth_header(
                                              self.user_with_permission.username,
                                              api_key_without_explicit_permissions
                                          )
                                      ))

    def test_login_with_no_api_access_default(self):
        api_key_with_no_access, _ = HQApiKey.objects.get_or_create(
            user=WebUser.get_django_user(self.user_with_permission_but_no_api_access)
        )
        self.assertAuthenticationFail(self.require_edit_data,
                                      self._get_request(
                                          domain=self.domain,
                                          HTTP_AUTHORIZATION=self._construct_api_auth_header(
                                              self.user_with_permission_but_no_api_access.username,
                                              api_key_with_no_access,
                                          )
                                      ))

    def test_login_with_wrong_permission(self):
        api_key_without_permissions, _ = HQApiKey.objects.get_or_create(
            user=WebUser.get_django_user(self.user_without_permission)
        )
        self.assertAuthenticationFail(self.require_edit_data,
                                      self._get_request(
                                          domain=self.domain,
                                          HTTP_AUTHORIZATION=self._construct_api_auth_header(
                                              self.user_without_permission.username,
                                              api_key_without_permissions
                                          )
                                      ))

    def test_login_with_wrong_permission_explicit_roles(self):
        api_key_with_explicit_permissions, _ = HQApiKey.objects.get_or_create(
            user=WebUser.get_django_user(self.user_without_permission),
            name='explicit_with_permission',
            role_id=self.role_with_permission.get_id,
        )
        api_key_without_explicit_permissions, _ = HQApiKey.objects.get_or_create(
            user=WebUser.get_django_user(self.user_without_permission),
            name='explicit_without_permission',
            role_id=self.role_without_permission.get_id,
        )
        # both of these should fail since the user shouldn't be allowed API access
        # to a role they don't have
        self.assertAuthenticationFail(self.require_edit_data,
                                      self._get_request(
                                          domain=self.domain,
                                          HTTP_AUTHORIZATION=self._construct_api_auth_header(
                                              self.user_without_permission.username,
                                              api_key_with_explicit_permissions
                                          )
                                      ))
        self.assertAuthenticationFail(self.require_edit_data,
                                      self._get_request(
                                          domain=self.domain,
                                          HTTP_AUTHORIZATION=self._construct_api_auth_header(
                                              self.user_without_permission.username,
                                              api_key_without_explicit_permissions
                                          )
                                      ))

    def test_explicit_role_wrong_domain(self):
        project = Domain.get_or_create_with_name('api-test-fail-2', is_active=True)
        self.addCleanup(project.delete)
        user = WebUser.create(self.domain, 'multi_domain_admin', '***', None, None, is_admin=True)
        user.add_domain_membership(project.name, is_admin=True)
        user.save()
        self.addCleanup(user.delete, self.domain, deleted_by=None)
        unscoped_api_key, _ = HQApiKey.objects.get_or_create(
            user=WebUser.get_django_user(user),
            name='unscoped',
        )
        # this key should only be able to access default project, not new one
        scoped_api_key, _ = HQApiKey.objects.get_or_create(
            user=WebUser.get_django_user(user),
            name='explicit_with_permission_wrong_domain',
            role_id=self.role_with_permission.get_id,
        )
        unscoped_auth_header = self._construct_api_auth_header(user.username, unscoped_api_key)
        scoped_auth_header = self._construct_api_auth_header(user.username, scoped_api_key)
        for domain in [self.domain, project.name]:
            self.assertAuthenticationSuccess(self.require_edit_data,
                                             self._get_request(
                                                 domain=domain,
                                                 HTTP_AUTHORIZATION=unscoped_auth_header))
        self.assertAuthenticationSuccess(self.require_edit_data,
                                         self._get_request(
                                             domain=self.domain,
                                             HTTP_AUTHORIZATION=scoped_auth_header
                                         ))
        self.assertAuthenticationFail(self.require_edit_data,
                                      self._get_request(
                                          domain=project.name,
                                          HTTP_AUTHORIZATION=scoped_auth_header
                                      ))

    def test_auth_type_basic(self):
        self.assertAuthenticationSuccess(
            self.require_edit_data,
            self._get_request(
                domain=self.domain,
                HTTP_AUTHORIZATION=self._construct_basic_auth_header(self.domain_admin.username, self.password)
            )
        )
