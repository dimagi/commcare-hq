from __future__ import print_function, unicode_literals

from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import Client

from corehq.apps.users.models import WebUser
from corehq.apps.app_manager.models import AppStructureRepeater
from corehq.apps.domain.models import Domain

class TestDomainViews(TestCase):
    def setUp(self):
        self.client = Client()

        self.domain = Domain(name="fandago", is_active=True)
        self.domain.save()

        self.username = 'bananafana'
        self.password = '*******'
        self.user = WebUser.create(self.domain.name, self.username, self.password)
        self.user.set_role(self.domain.name, 'admin')
        self.user.save()

    def tearDown(self):
        self.user.delete()
        self.domain.delete()
        
    def test_add_repeater(self):
        forwarding_url = 'https://example.com/forwarding'

        self.client.login(username=self.username, password=self.password)

        post_url = reverse('add_repeater', kwargs={'domain': self.domain.name, 'repeater_type': 'AppStructureRepeater'})
        response = self.client.post(post_url, {'url': forwarding_url}, follow=True)
        self.assertEqual(response.status_code, 200)

        self.client.logout()
        
        app_structure_repeaters = AppStructureRepeater.by_domain(self.domain.name)
        self.assertEqual(len(app_structure_repeaters), 1)

        for app_structure_repeater in app_structure_repeaters:
            app_structure_repeater.delete()
