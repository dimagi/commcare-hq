from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.test.client import Client
from corehq.util.test_utils import flag_enabled
from corehq.apps.users.models import CouchUser
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.decorators import _two_factor_required, two_factor_check
from mock import mock
import json


class TestTwoFactorCheck(TestCase):

    def setUp(self):
        self.domain = create_domain("test_domain")
        self.domain.two_factor_auth = False
        self.request = self.create_request(request_url="/account/",
                                           username="test0@test.com",
                                           password="123",
                                           )

    @classmethod
    def create_request(cls, request_url, username, password):
        # Initialize request
        request = Client().get(request_url).wsgi_request
        # Create user
        request.user = get_user_model().objects.create_user(username=username,
                                                            email=username,
                                                            password=password)
        # Create couch user
        request.couch_user = CouchUser()
        # Login
        assert Client().login(username=username, password=password)
        return request
    #
    @flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
    def test_two_factor_required_with_feature_flag(self):
        view_func = "dummy_view_func"
        request = self.request
        two_factor_required_bool = _two_factor_required(view_func, self.domain, request.couch_user)
        self.assertTrue(two_factor_required_bool)

    def test_two_factor_required_without_feature_flag(self):
        view_func = "dummy_view_func"
        request = self.request
        two_factor_required_bool = _two_factor_required(view_func, self.domain,
                                                        request.couch_user)
        self.assertFalse(two_factor_required_bool)

    @flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
    def test_two_factor_check_with_feature_flag(self):
        def func_to_check_2fa_on(*_):
            return 'Function was called!'

        request = self.request
        api_key = None
        view_func = "dummy_view_func"
        two_factor_check_fn = two_factor_check(view_func, api_key)
        function_getting_checked_with_auth = two_factor_check_fn(func_to_check_2fa_on)
        with mock.patch('corehq.apps.domain.decorators._ensure_request_couch_user',
                        return_value=request.couch_user):
            response = function_getting_checked_with_auth(request, self.domain.name)
            data = json.loads(response.content)
            self.assertDictEqual(data, {'error': 'must send X-CommcareHQ-OTP header'})

    def test_two_factor_check_without_feature_flag(self):
        def func_to_check_2fa_on(*_):
            return 'Function was called!'

        request = self.request
        api_key = None
        view_func = "dummy_view_func"
        two_factor_check_fn = two_factor_check(view_func, api_key)
        function_getting_checked_with_auth = two_factor_check_fn(func_to_check_2fa_on)
        with mock.patch('corehq.apps.domain.decorators._ensure_request_couch_user',
                        return_value=request.couch_user):
            response = function_getting_checked_with_auth(request, self.domain.name)
            self.assertEqual(response, 'Function was called!')
