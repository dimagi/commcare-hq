from django.test import SimpleTestCase, override_settings

from corehq.apps.hqwebapp.login_utils import get_custom_login_page


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
