from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

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
        user = self.create_user()
        self.assertTrue(is_logged_in(self.make_request(user)))

    def test_returns_false_if_user_is_not_authenticated(self):
        self.assertFalse(is_logged_in(self.make_request(AnonymousUser())))

    def test_returns_false_if_sso_session_is_not_authenticated(self):
        request = self.make_request(AnonymousUser(), session={'samlSessionIndex': '_abc123'})
        self.assertFalse(is_logged_in(request))

    def test_returns_true_if_user_with_2fa_is_authenticated_and_verified(self):
        user = self.create_user(has_device=True, is_verified=True)
        self.assertTrue(is_logged_in(self.make_request(user)))

    def test_returns_false_if_user_with_2fa_is_authenticated_but_not_verified(self):
        user = self.create_user(has_device=True, is_verified=False)
        self.assertFalse(is_logged_in(self.make_request(user)))

    def test_returns_true_if_user_with_2fa_is_not_verified_but_using_saml(self):
        user = self.create_user(has_device=True, is_verified=False)
        request = self.make_request(user, session={'samlSessionIndex': '_abc123'})
        self.assertTrue(is_logged_in(request))

    def test_returns_true_if_user_with_2fa_is_not_verified_but_using_oidc(self):
        user = self.create_user(has_device=True, is_verified=False)
        request = self.make_request(user, session={'oidc_state': 'abc123'})
        self.assertTrue(is_logged_in(request))

    @staticmethod
    def create_user(has_device=False, is_verified=False):
        user = User(username="test-user", password="abc123")
        user.save()
        user.is_verified = lambda: is_verified
        if has_device:
            TOTPDevice(user=user, name='default', confirmed=True).save()
        return user

    @staticmethod
    def make_request(user, session=None):
        request = RequestFactory().get('/accounts/login/')
        request.user = user
        request.session = session or {}
        return request
