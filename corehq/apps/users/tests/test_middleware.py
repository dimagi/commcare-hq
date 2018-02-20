from django.test import TestCase
from django.test.client import Client

from corehq.util.test_utils import flag_enabled

from corehq.apps.users.middleware import Enforce2FAMiddleware


class TestTwoFactorMiddleware(TestCase):

    @flag_enabled('TWO_FACTOR_SUPERUSER_ROLLOUT')
    def test_process_view(self):
        test_url = "http://commcarehq.org/?domain=joto&case_type=teddiursa"
        request = Client().get(test_url).wsgi_request

        # request = 5

        a = Enforce2FAMiddleware().process_view(request, "view_func", "view_args", "view_kwargs")
        self.assertEqual(a, 9999)


