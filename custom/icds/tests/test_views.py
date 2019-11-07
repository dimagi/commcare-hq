from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse


class TestViews(TestCase):

    @override_settings(CUSTOM_LANDING_TEMPLATE=None, SERVER_ENVIRONMENT='production')
    def test_normal_login(self):
        response = self.client.get(reverse("login"), follow=False)
        self._assertProductionLogin(response)

    @override_settings(CUSTOM_LANDING_TEMPLATE='icds/login.html', SERVER_ENVIRONMENT='production')
    def test_custom_login_old_format(self):
        response = self.client.get(reverse("login"), follow=False)
        self._assertICDSLogin(response)

    @override_settings(CUSTOM_LANDING_TEMPLATE={"default": 'icds/login.html'}, SERVER_ENVIRONMENT='production')
    def test_custom_login(self):
        response = self.client.get(reverse("login"), follow=False)
        self.assertEqual(response.status_code, 200)
        self._assertICDSLogin(response)

    @override_settings(CUSTOM_LANDING_TEMPLATE={'nodefault': 'icds/login.html'}, SERVER_ENVIRONMENT='production')
    def test_custom_login_missing_key(self):
        response = self.client.get(reverse("login"), follow=False)
        self._assertProductionLogin(response)

    def _assertProductionLogin(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dimagi.com')
        self.assertNotContains(response, 'Ministry of Women and Child Development')

    def _assertICDSLogin(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ministry of Women and Child Development')
        self.assertNotContains(response, 'dimagi.com')
