from django.test import TestCase
from django.test.client import Client
from django_otp.middleware import OTPMiddleware
from django.contrib.auth.middleware import AuthenticationMiddleware

from corehq.util.test_utils import flag_enabled
from corehq.apps.users.models import CouchUser, User
from corehq.apps.users.middleware import Enforce2FAMiddleware
from corehq.apps.users.tests.utils import UserMixin as test_utils

from two_factor.utils import default_device
from django_otp import DEVICE_ID_SESSION_KEY


class TestTwoFactorMiddleware(TestCase):

    def setUp(self):
        self.account_url = "/account/"
        self.non_account_url = "/not_account/"

    def process_2fa_middleware(self, request):
        AuthenticationMiddleware().process_request(request)
        OTPMiddleware().process_request(request)

    def enable_otp(self, request):
        request.user.totpdevice.create(name='default')
        print("&&#&$^#&$^#&$" + request.user.otp_device)

    # def login_user(self, user, username, password):
    #     self.client.login(username=username, password=password)
    #     if default_device(user):
    #         session = self.client.session
    #         session[DEVICE_ID_SESSION_KEY] = default_device(user).persistent_id
    #         session.save()

    @flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
    def test_process_view(self):
        my_test_utils = test_utils()

        request = Client().get(self.account_url).wsgi_request
        request.couch_user = CouchUser()
        request.user = my_test_utils.create_user() #User.objects.create_user(username="test_username", email="test@example.com", password="123")
        my_test_utils.enable_otp(request.user)

        # AuthenticationMiddleware().process_request(request)
        OTPMiddleware().process_request(request)

        my_test_utils.login_user(request.user)
        request.user.save()

        print("@#$@#$OTP DEVICE BEFORE? {}".format(request.user.otp_device))

        request.user.otp_device = "NOT NONE"
        print("@#$@#$OTP DEVICE AFTER? {}".format(request.user.otp_device))



        # self.enable_otp(request)



        # self.process_2fa_middleware(request)



        response = Enforce2FAMiddleware().process_view(request, "view_func", "view_args", "view_kwargs")

        self.assertEqual(response.status_code, 403)

    def test_verified(self):
        # test_utils().setUp()
        my_test_utils = test_utils()
        user = my_test_utils.create_user()
        my_test_utils.enable_otp(user)  # create OTP before login, so verified
        my_test_utils.login_user(user)
        print(user.is_verified())
        # self.assertEqual(response.status_code, 200)


