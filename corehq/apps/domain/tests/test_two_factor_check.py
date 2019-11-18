import json

from django.test import RequestFactory, TestCase

from mock import Mock, mock

from corehq.apps.domain.decorators import (
    OTP_AUTH_FAIL_RESPONSE,
    _two_factor_required,
    two_factor_check,
)
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CouchUser
from corehq.util.test_utils import flag_enabled


class TestTwoFactorCheck(TestCase):
    domain_name = 'test_domain'

    def setUp(self):

        self.domain = create_domain(self.domain_name)
        self.domain.two_factor_auth = False
        self.request = self.create_request(request_url='/account/')

    def tearDown(self):
        Domain.get_by_name(self.domain_name).delete()

    @classmethod
    def create_request(cls, request_url):
        request = RequestFactory().get(request_url)
        request.couch_user = CouchUser()
        return request

    @flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
    def test_two_factor_required_with_feature_flag(self):
        view_func = 'dummy_view_func'
        request = self.request
        two_factor_required_bool = _two_factor_required(view_func, self.domain, request.couch_user)
        self.assertTrue(two_factor_required_bool)

    def test_two_factor_required_without_feature_flag(self):
        view_func = 'dummy_view_func'
        request = self.request
        two_factor_required_bool = _two_factor_required(view_func, self.domain,
                                                        request.couch_user)
        self.assertFalse(two_factor_required_bool)

    @flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
    def test_two_factor_check_with_feature_flag(self):
        mock_fn_to_call = Mock(return_value='Function was called!')
        mock_fn_to_call.__name__ = 'test_name'
        request = self.request
        api_key = None
        view_func = 'dummy_view_func'
        two_factor_check_fn = two_factor_check(view_func, api_key)
        function_getting_checked_with_auth = two_factor_check_fn(mock_fn_to_call)
        with mock.patch('corehq.apps.domain.decorators._ensure_request_couch_user',
                        return_value=request.couch_user):
            response = function_getting_checked_with_auth(request, self.domain.name)
            self.assertEqual(response.status_code, 401)
            mock_fn_to_call.assert_not_called()

            data = json.loads(response.content)
            self.assertDictEqual(data, OTP_AUTH_FAIL_RESPONSE)

    def test_two_factor_check_without_feature_flag(self):
        mock_fn_to_call = Mock(return_value="Function was called!")
        mock_fn_to_call.__name__ = 'test_name'
        request = self.request
        api_key = None
        view_func = 'dummy_view_func'
        two_factor_check_fn = two_factor_check(view_func, api_key)
        function_getting_checked_with_auth = two_factor_check_fn(mock_fn_to_call)
        with mock.patch('corehq.apps.domain.decorators._ensure_request_couch_user',
                        return_value=request.couch_user):
            response = function_getting_checked_with_auth(request, self.domain.name)
            self.assertEqual(response, 'Function was called!')
            mock_fn_to_call.assert_called_once()
