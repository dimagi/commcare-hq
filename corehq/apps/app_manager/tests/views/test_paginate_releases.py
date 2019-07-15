from __future__ import absolute_import
from __future__ import unicode_literals

from django.urls import reverse
from django.test import TestCase
from django.test.client import Client

from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.apps.app_manager.models import Application
from corehq.elastic import send_to_elasticsearch, get_es_new
from corehq.util.elastic import delete_es_index
from corehq.util.test_utils import flag_enabled
from corehq.pillows.mappings.app_mapping import APP_INDEX_INFO


class TestPaginateReleases(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestPaginateReleases, cls).setUpClass()
        cls.client = Client()

        cls.domain_name = "fandago"
        cls.domain = Domain(name=cls.domain_name, is_active=True)
        cls.domain.save()

        cls.username = 'bananafana'
        cls.password = '*******'
        cls.user = WebUser.create(cls.domain.name, cls.username, cls.password, is_admin=True)
        cls.user.eula.signed = True
        cls.user.save()

        cls.app = Application.new_app(domain=cls.domain_name, name="cheeto")
        cls.app.target_commcare_flavor = 'commcare_lts'
        cls.app.save()
        cls.app_build = cls.app.make_build()
        cls.app_build.is_released = True
        cls.app_build.save()

        # publish app and build to ES
        es = get_es_new()
        initialize_index_and_mapping(es, APP_INDEX_INFO)
        send_to_elasticsearch('apps', cls.app.to_json())
        send_to_elasticsearch('apps', cls.app_build.to_json())
        es.indices.refresh(APP_INDEX_INFO.index)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.domain.delete()
        delete_es_index(APP_INDEX_INFO.index)
        super(TestPaginateReleases, cls).tearDownClass()

    def get_commcare_flavor_on_releases_page(self, only_released=False):
        url = reverse('paginate_releases', args=(self.domain_name, self.app.get_id))
        if only_released:
            url += "?only_show_released=true"
        response = self.client.get(url)
        return response.json()['apps'][0]['commcare_flavor']

    def test_commcare_flavor(self):
        self.client.login(username=self.username, password=self.password)
        # Couch View Test
        self.assertEqual(self.get_commcare_flavor_on_releases_page(), None)
        # ES Search Test
        self.assertEqual(self.get_commcare_flavor_on_releases_page(only_released=True), None)
        with flag_enabled('TARGET_COMMCARE_FLAVOR'):
            # Couch View Test
            self.assertEqual(self.get_commcare_flavor_on_releases_page(), 'commcare_lts')
            # ES Search Test
            self.assertEqual(self.get_commcare_flavor_on_releases_page(only_released=True), 'commcare_lts')
