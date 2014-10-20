from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import Client

from corehq.apps.users.models import WebUser
from corehq.apps.domain.shortcuts import create_domain


class ForwardingViewTest(TestCase):
    def setUp(self):
        self.domain = create_domain("submit")
        self.couch_user = WebUser.create(None, "forwarding_test", "foobar")
        self.couch_user.add_domain_membership(self.domain.name, is_admin=True)
        self.couch_user.save()
        self.client = Client()
        self.client.login(**{'username': 'forwarding_test', 'password': 'foobar'})

    def tearDown(self):
        self.couch_user.delete()
        self.domain.delete()

    def _test_get(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_form_repeater(self):
        self._test_get(
            reverse('add_form_repeater', args=[self.domain])
        )

    def test_case_repeater(self):
        self._test_get(
            reverse('add_repeater', args=[self.domain, 'CaseRepeater'])
        )

    def test_short_form_repeater(self):
        self._test_get(
            reverse('add_repeater', args=[self.domain, 'ShortFormRepeater'])
        )

    def test_app_structure_repeater(self):
        self._test_get(
            reverse('add_repeater', args=[self.domain, 'AppStructureRepeater'])
        )
