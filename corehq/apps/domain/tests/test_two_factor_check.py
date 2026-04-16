import json
from unittest.mock import Mock, patch

from django.test import RequestFactory, TestCase, override_settings

from corehq.apps.domain.decorators import (
    OTP_AUTH_FAIL_RESPONSE,
    _two_factor_required,
    two_factor_check,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.sso.tests.generator import create_request_session
from corehq.apps.users.models import CouchUser


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

    @patch('corehq.apps.domain.decorators._ensure_request_couch_user')
    @patch('corehq.apps.domain.decorators.Domain.get_by_name', new=lambda _: Mock(two_factor_auth=True))
    def test_skip_two_factor_check_sets_bypass(self, mock_ensure_couch_user):
        """When skip_two_factor_check is set (e.g. API key auth via basic auth),
        two_factor_check should set bypass_two_factor
        """
        mock_ensure_couch_user.return_value = self.request.couch_user
        self.request.skip_two_factor_check = True

        @two_factor_check('dummy_view', api_key=False)
        def view(request, domain):
            return request

        request = view(self.request, 'test_domain')
        self.assertTrue(
            getattr(request, 'bypass_two_factor', False),
            "bypass_two_factor should be set when skip_two_factor_check is True",
        )
