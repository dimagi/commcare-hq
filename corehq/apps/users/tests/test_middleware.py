from django.test import TestCase
from django.test.client import Client
from django_otp.middleware import OTPMiddleware
from django.contrib.auth.middleware import AuthenticationMiddleware

from corehq.util.test_utils import flag_enabled
from corehq.apps.users.models import CouchUser
from corehq.apps.users.middleware import Enforce2FAMiddleware


class TestTwoFactorMiddleware(TestCase):

    @flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
    def test_process_view(self):

        my_client = Client()

        test_url = "http://commcarehq.org/otp_admin"
        request = my_client.get(test_url).wsgi_request

        # Install the two 2fa middlewares
        AuthenticationMiddleware().process_request(request)
        OTPMiddleware().process_request(request)

        request.couch_user = CouchUser()

        response = Enforce2FAMiddleware().process_view(request, "view_func", "view_args", "view_kwargs")
        
        self.assertEqual(response.status_code, 403)


