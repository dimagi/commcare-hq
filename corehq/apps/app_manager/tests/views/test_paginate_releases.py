from __future__ import absolute_import
from __future__ import unicode_literals

from django.urls import reverse
from django.test import TestCase
from django.test.client import Client

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.apps.app_manager.models import Application
from corehq.util.test_utils import flag_enabled


class TestPaginateReleases(TestCase):
    def setUp(self):
        self.client = Client()

        self.domain_name = "fandago"
        self.domain = Domain(name=self.domain_name, is_active=True)
        self.domain.save()

        self.username = 'bananafana'
        self.password = '*******'
        self.user = WebUser.create(self.domain.name, self.username, self.password, is_admin=True)
        self.user.eula.signed = True
        self.user.save()

        self.app = Application.new_app(domain=self.domain_name, name="cheeto")
        self.app.target_commcare_flavor = 'commcare_lts'
        self.app.save()
        self.app_build = self.app.make_build()
        self.app_build.save()

    def tearDown(self):
        self.user.delete()
        self.domain.delete()

    def test_target_commcare_flavor(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse('paginate_releases', args=(self.domain_name, self.app.get_id)))
        self.assertEqual(response.json()['apps'][0]['target_commcare_flavor'], 'none')

        with flag_enabled('TARGET_COMMCARE_FLAVOR'):
            response = self.client.get(reverse('paginate_releases', args=(self.domain_name, self.app.get_id)))
            self.assertEqual(response.json()['apps'][0]['target_commcare_flavor'], 'commcare_lts')
