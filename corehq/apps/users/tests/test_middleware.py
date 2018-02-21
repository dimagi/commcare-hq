from django.test import TestCase
from django.test.client import Client
from django_otp.middleware import OTPMiddleware
from corehq.util.test_utils import flag_enabled
from corehq.apps.users.models import CouchUser
from corehq.apps.users.middleware import Enforce2FAMiddleware
from corehq.apps.users.tests.utils import UserMixin as test_utils

import mock


class TestTwoFactorMiddleware(TestCase):

    def setUp(self):
        self.account_url = "/account/"
        self.non_account_url = "/not_account/"

    @flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
    def test_process_view(self):
        my_test_utils = test_utils()

        request = Client().get(self.account_url).wsgi_request
        request.couch_user = CouchUser()

        request.user = my_test_utils.create_user()
        my_test_utils.enable_otp(request.user)

        OTPMiddleware().process_request(request)

        my_test_utils.login_user(request.user)
        request.user.save()

        request.user.otp_device = "NOT NONE"
        with mock.patch('corehq.apps.users.models.CouchUser.two_factor_disabled', new_callable=mock.PropertyMock,
                        return_value=68):
            response = Enforce2FAMiddleware().process_view(request, "view_func", "view_args", "view_kwargs")

        self.assertEqual(response.status_code, 403)
