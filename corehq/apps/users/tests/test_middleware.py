from django.test import TestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url
from django_otp import DEVICE_ID_SESSION_KEY
from django.test.client import Client

from django_otp.middleware import OTPMiddleware

from corehq.util.test_utils import flag_enabled
from corehq.apps.users.models import CouchUser
from corehq.apps.users.middleware import Enforce2FAMiddleware

import mock


class TestTwoFactorMiddleware(TestCase):

    def setUp(self):
        self.account_request = Client().get("/account/").wsgi_request
        self.create_and_login_user(self.account_request)

        self.non_account_request = Client().get("/not_account/").wsgi_request
        self.create_and_login_user(self.non_account_request)

    def create_and_login_user(self, request, username='test@example.com', password='secret'):
        # Create user and couch user
        request.user = get_user_model().objects.create_user(username=username, email=username, password=password)
        username = request.user.get_username()
        request.couch_user = CouchUser()
        # Login
        assert Client().login(username=username, password=password)

    def enable_two_factor_for_user(self, request):
        OTPMiddleware().process_request(request)
        request.user.otp_device = "test_device"

    @flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
    def test_process_view(self):
        request = self.account_request
        # self.create_and_login_user(request)
        self.enable_two_factor_for_user(request)
        with mock.patch('corehq.apps.users.models.CouchUser.two_factor_disabled', new_callable=mock.PropertyMock,
                        return_value=68):
            response = Enforce2FAMiddleware().process_view(request, "test_view_func", "test_view_args",
                                                           "test_view_kwargs")
        self.assertEqual(response.status_code, 403)
