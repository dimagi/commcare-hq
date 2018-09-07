from __future__ import absolute_import
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse


class TestViews(TestCase):
    @override_settings(CUSTOM_LANDING_TEMPLATE='icds/login.html')
    def test_custom_login(self):
        response = self.client.get(reverse("login"), follow=False)
        self.assertEqual(response.status_code, 200)
