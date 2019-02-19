from __future__ import absolute_import
from __future__ import unicode_literals

from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse


class TestViews(TestCase):
    @override_settings(CUSTOM_LANDING_TEMPLATE='icds/login.html')
    def test_custom_login_old_format(self):
        response = self.client.get(reverse("login"), follow=False)
        self.assertEqual(response.status_code, 200)

    @override_settings(CUSTOM_LANDING_TEMPLATE={"default": 'icds/login.html'})
    def test_custom_login(self):
        response = self.client.get(reverse("login"), follow=False)
        self.assertEqual(response.status_code, 200)
