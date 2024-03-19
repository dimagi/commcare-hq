from django.contrib.auth.models import AnonymousUser, User
from django.test import SimpleTestCase, TestCase, override_settings

from django_otp.plugins.otp_totp.models import TOTPDevice

from corehq.apps.hqwebapp.login_utils import (
    get_custom_login_page,
    is_logged_in,
)


class TestCustomLogin(SimpleTestCase):

    @override_settings(CUSTOM_LANDING_TEMPLATE=None)
    def test_nothing_configured(self):
        self.assertEqual(None, get_custom_login_page('example.com'))

    @override_settings(CUSTOM_LANDING_TEMPLATE='custom/login.html')
    def test_string_configured(self):
        self.assertEqual('custom/login.html', get_custom_login_page('example.com'))

    @override_settings(CUSTOM_LANDING_TEMPLATE={'example.com': 'custom/login.html'})
    def test_dict_match(self):
        self.assertEqual('custom/login.html', get_custom_login_page('example.com'))

    @override_settings(CUSTOM_LANDING_TEMPLATE={'example.com': 'custom/login.html'})
    def test_dict_mismatch(self):
        self.assertEqual(None, get_custom_login_page('commcarehq.org'))

    @override_settings(CUSTOM_LANDING_TEMPLATE={'example.com': 'custom/login.html',
                                                'default': 'normal/login.html'})
    def test_dict_default(self):
        self.assertEqual('custom/login.html', get_custom_login_page('example.com'))
        self.assertEqual('normal/login.html', get_custom_login_page('commcarehq.org'))


class TestIsLoggedIn(TestCase):

    def test_returns_true_if_user_without_2fa_is_authenticated(self):
        user = User(username="test-user", password="abc123")
        self.assertTrue(is_logged_in(user))

    def test_returns_false_if_user_without_2fa_is_not_authenticated(self):
        user = AnonymousUser()
        self.assertFalse(is_logged_in(user))

    def test_returns_true_if_user_with_2fa_is_authenticated_and_verified(self):
        user = User(username="test-user", password="abc123")
        user.save()
        user.is_verified = lambda: True
        self.setup_two_factor_device(user)
        self.assertTrue(is_logged_in(user))

    def test_returns_false_if_user_with_2fa_is_authenticated_but_not_verified(self):
        user = User(username="test-user", password="abc123")
        user.save()
        user.is_verified = lambda: False
        self.setup_two_factor_device(user)
        self.assertFalse(is_logged_in(user))

    @staticmethod
    def setup_two_factor_device(user):
        device = TOTPDevice(user=user, name='default', confirmed=True)
        device.save()
