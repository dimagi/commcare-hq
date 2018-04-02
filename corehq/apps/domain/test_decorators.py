from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.test.client import Client
from corehq.util.test_utils import flag_enabled
from corehq.apps.users.models import CouchUser
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.decorators import _two_factor_required


class TestDecorators(TestCase):

    def setUp(self):
        self.domain = create_domain("test_domain")
        self.domain.two_factor_auth = False
        self.request = self.create_request(request_url="/account/",
                                           username="test0@test.com",
                                           password="123",
                                           )

    @classmethod
    def create_request(request_url, username, password):
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

    @classmethod
    def enable_two_factor_for_user(cls, request):
        request.user.otp_device = "test_device"

    @flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
    def test_two_factor_required_with_feature_flag(self):
        view_func=5
        request = self.request
        self.enable_two_factor_for_user(request)
        two_factor_required_bool = _two_factor_required(view_func, self.domain, request.couch_user)
        self.assertEqual(two_factor_required_bool, True)

    def test_two_factor_required_without_feature_flag(self):
        view_func = 5
        request = self.request
        self.enable_two_factor_for_user(request)
        two_factor_required_bool = _two_factor_required(view_func, self.domain,
                                                        request.couch_user)
        self.assertEqual(two_factor_required_bool, False)
