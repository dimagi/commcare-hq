from unittest.case import TestCase
from unittest.mock import Mock, patch

from django.urls import reverse, resolve


class TestUrls(TestCase):

    def test_url_for_hubspot(self):
        url = reverse('hubspot_click_deploy')
        expected_url = r'/analytics/hubspot/click-deploy/'

        self.assertEqual(url, expected_url)

    def test_url_for_greenhouse(self):
        url = reverse('greenhouse_candidate')
        expected_url = r'/analytics/greenhouse/candidate/'

        self.assertEqual(url, expected_url)
