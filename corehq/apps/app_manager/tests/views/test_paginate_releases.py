from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    get_simple_form,
    patch_validate_xform,
)
from corehq.apps.domain.models import Domain
from corehq.apps.es.apps import app_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled


@es_test(requires=[app_adapter], setup_class=True)
class TestPaginateReleases(TestCase):
    @classmethod
    @patch_validate_xform()
    def setUpClass(cls):
        super(TestPaginateReleases, cls).setUpClass()
        cls.client = Client()

        cls.domain_name = "fandago"
        cls.domain = Domain.get_or_create_with_name(cls.domain_name, is_active=True)

        cls.username = 'bananafana'
        cls.password = '*******'
        cls.user = WebUser.create(cls.domain.name, cls.username, cls.password, None, None, is_admin=True)
        cls.user.eula.signed = True
        cls.user.save()

        factory = AppFactory(cls.domain_name, name="cheeto")
        m0, f0 = factory.new_basic_module("register", "cheeto")
        f0.source = get_simple_form(xmlns=f0.unique_id)
        cls.app = factory.app
        cls.app.target_commcare_flavor = 'commcare_lts'
        cls.app.save()
        cls.app_build = cls.app.make_build()
        cls.app_build.is_released = True
        cls.app_build.save()

        # publish app and build to ES
        app_adapter.bulk_index([cls.app, cls.app_build], refresh=True)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()
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
