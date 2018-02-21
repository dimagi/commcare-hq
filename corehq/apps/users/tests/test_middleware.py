from django.test import TestCase
from django.contrib.auth import get_user_model
from django.test.client import Client

from django_otp.middleware import OTPMiddleware

from corehq.util.test_utils import flag_enabled
from corehq.apps.users.models import CouchUser
from corehq.apps.users.middleware import Enforce2FAMiddleware

import mock


class TestTwoFactorMiddleware(TestCase):

    def setUp(self):
        self.account_request = self.create_request(request_url="/account/", username="test_1@test.com", password="123")

        self.non_account_request = self.create_request(request_url="/not_account/", username="test_2@test.com", password="123")

    @classmethod
    def create_request(cls, request_url, username, password):
        # Create request
        request = Client().get(request_url).wsgi_request
        # Create user and couch user
        request.user = get_user_model().objects.create_user(username=username, email=username, password=password)
        username = request.user.get_username()
        request.couch_user = CouchUser()
        # Login
        assert Client().login(username=username, password=password)
        # Activate middleware
        OTPMiddleware().process_request(request)
        return request

    @classmethod
    def enable_two_factor_for_user(cls, request):
        request.user.otp_device = "test_device"

    @flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
    def test_process_view_permission_denied(self):
        request = self.non_account_request
        with mock.patch('corehq.apps.users.models.CouchUser.two_factor_disabled',
                        new_callable=mock.PropertyMock,
                        return_value=False):
            response = Enforce2FAMiddleware().process_view(request, "test_view_func",
                                                           "test_view_args", "test_view_kwargs")
        self.assertEqual(response.status_code, 403)

    @flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
    def test_process_view_two_factor_enabled(self):
        request = self.non_account_request
        self.enable_two_factor_for_user(request)
        with mock.patch('corehq.apps.users.models.CouchUser.two_factor_disabled',
                        new_callable=mock.PropertyMock,
                        return_value=False):
            response = Enforce2FAMiddleware().process_view(request, "test_view_func",
                                                           "test_view_args", "test_view_kwargs")
        self.assertEqual(response, None)

    @flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
    def test_process_view_couch_user_two_factor_disabled(self):
        request = self.non_account_request
        with mock.patch('corehq.apps.users.models.CouchUser.two_factor_disabled',
                        new_callable=mock.PropertyMock,
                        return_value=True):
            response = Enforce2FAMiddleware().process_view(request, "test_view_func",
                                                           "test_view_args", "test_view_kwargs")
        self.assertEqual(response, None)

    @flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
    def test_process_view_account_url(self):
        request = self.account_request
        self.enable_two_factor_for_user(request)
        with mock.patch('corehq.apps.users.models.CouchUser.two_factor_disabled',
                        new_callable=mock.PropertyMock,
                        return_value=False):
            response = Enforce2FAMiddleware().process_view(request, "test_view_func",
                                                           "test_view_args", "test_view_kwargs")
        self.assertEqual(response, None)
