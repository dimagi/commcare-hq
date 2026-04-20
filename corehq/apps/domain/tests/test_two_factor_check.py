import base64
import json
from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase, override_settings

from corehq.apps.domain.decorators import (
    OTP_AUTH_FAIL_RESPONSE,
    _two_factor_required,
    api_auth,
    two_factor_check,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.sso.tests.generator import create_request_session
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import CouchUser, HQApiKey, HqPermissions, WebUser


class TestTwoFactorRequired(TestCase):
    domain_name = 'test_domain'

    def setUp(self):
        self.domain = create_domain(self.domain_name)
        self.domain.two_factor_auth = False
        self.addCleanup(self.domain.delete)
        self.request = self.create_request(request_url='/account/')

    @classmethod
    def create_request(cls, request_url):
        request = RequestFactory().get(request_url)
        request.couch_user = CouchUser()
        return request

    @override_settings(REQUIRE_TWO_FACTOR_FOR_SUPERUSERS=True)
    def test_two_factor_required_for_superuser(self):
        self.request.couch_user.is_superuser = True
        view_func = 'dummy_view_func'
        two_factor_required_bool = _two_factor_required(
            view_func, self.domain, self.request
        )
        self.assertTrue(two_factor_required_bool)

    @override_settings(REQUIRE_TWO_FACTOR_FOR_SUPERUSERS=False)
    def test_two_factor_not_required_for_superuser(self):
        self.request.couch_user.is_superuser = True
        view_func = 'dummy_view_func'
        two_factor_required_bool = _two_factor_required(
            view_func, self.domain, self.request
        )
        self.assertFalse(two_factor_required_bool)

    def test_two_factor_not_required_with_sso_request(self):
        view_func = 'dummy_view_func'
        request = self.request
        create_request_session(request, use_saml_sso=True)
        two_factor_required_bool = _two_factor_required(
            view_func, self.domain, request
        )
        self.assertFalse(two_factor_required_bool)

    def test_two_factor_required_for_domain(self):
        self.domain.two_factor_auth = True
        self.domain.save()
        view_func = 'dummy_view_func'
        request = self.request
        two_factor_required_bool = _two_factor_required(
            view_func, self.domain, request
        )
        self.assertTrue(two_factor_required_bool)


class TestTwoFactorCheck(TestCase):
    domain_name = 'test_domain'

    def setUp(self):
        self.domain = create_domain(self.domain_name)
        self.domain.two_factor_auth = False
        self.addCleanup(self.domain.delete)
        self.request = self.create_request(request_url='/account/')

    @classmethod
    def create_request(cls, request_url):
        request = RequestFactory().get(request_url)
        request.couch_user = CouchUser()
        return request

    def test_successful_two_factor_check(self):
        mock_fn_to_call = Mock(return_value="Function was called!")
        mock_fn_to_call.__name__ = 'test_name'
        api_key = None
        view_func = 'dummy_view_func'
        two_factor_check_fn = two_factor_check(view_func, api_key)
        function_getting_checked_with_auth = two_factor_check_fn(
            mock_fn_to_call
        )
        with patch(
            'corehq.apps.domain.decorators._ensure_request_couch_user',
            return_value=self.request.couch_user,
        ):
            response = function_getting_checked_with_auth(
                self.request, self.domain.name
            )
            self.assertEqual(response, 'Function was called!')
            mock_fn_to_call.assert_called_once()

    @override_settings(REQUIRE_TWO_FACTOR_FOR_SUPERUSERS=True)
    def test_failed_two_factor_check(self):
        self.request.couch_user.is_superuser = True
        mock_fn_to_call = Mock(return_value='Function was called!')
        mock_fn_to_call.__name__ = 'test_name'
        api_key = None
        view_func = 'dummy_view_func'
        two_factor_check_fn = two_factor_check(view_func, api_key)
        function_getting_checked_with_auth = two_factor_check_fn(
            mock_fn_to_call
        )
        with patch(
            'corehq.apps.domain.decorators._ensure_request_couch_user',
            return_value=self.request.couch_user,
        ):
            response = function_getting_checked_with_auth(
                self.request, self.domain.name
            )
            self.assertEqual(response.status_code, 401)
            mock_fn_to_call.assert_not_called()

            data = json.loads(response.content)
            self.assertDictEqual(data, OTP_AUTH_FAIL_RESPONSE)


class TestApiKeyBasicAuthWithTwoFactor(TestCase):
    domain_name = 'two-factor-api-test'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(cls.domain_name)
        cls.addClassCleanup(cls.domain.delete)
        cls.domain.two_factor_auth = True
        cls.domain.save()
        cls.user = WebUser.create( cls.domain_name, 'test@dimagi.com', 'password', None, None, is_admin=True,)
        cls.addClassCleanup(cls.user.delete, cls.domain_name, deleted_by=None)
        cls.api_key = HQApiKey.objects.create(user=cls.user.get_django_user()).plaintext_key

    def test_api_key_basic_auth_with_two_factor_domain(self):
        encoded_creds = base64.b64encode(f'test@dimagi.com:{self.api_key}'.encode()).decode()
        request = RequestFactory().get(
            f'/a/{self.domain_name}/api/case/v2/',
            HTTP_AUTHORIZATION=f'Basic {encoded_creds}',
        )
        request.user = AnonymousUser()  # User hasn't been established yet

        @api_auth(allow_creds_in_data=False)
        @require_permission(HqPermissions.edit_data)
        def view(request, domain):
            from django.http import HttpResponse
            return HttpResponse('ok')

        response = view(request, self.domain_name)
        self.assertEqual(response.status_code, 200)
