
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from bs4 import BeautifulSoup
from mock import patch

from corehq.apps.app_manager.models import APP_V1, Application
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views.exchange import CreateNewExchangeSnapshotView
from corehq.apps.users.models import WebUser
from corehq.motech.repeaters.models import AppStructureRepeater
from corehq.util.test_utils import teardown


class TestDomainViews(TestCase):

    def setUp(self):
        self.client = Client()

        self.domain = Domain(name="fandago", is_active=True)
        self.domain.save()

        self.username = 'bananafana'
        self.password = '*******'
        self.user = WebUser.create(self.domain.name, self.username, self.password, is_admin=True)
        self.user.eula.signed = True
        self.user.save()

        self.app = Application.new_app(domain="fandago", name="cheeto")
        self.app.save()

    def tearDown(self):
        self.user.delete()
        self.domain.delete()
        
    def test_allow_domain_requests(self):
        self.client.login(username=self.username, password=self.password)

        public_domain = Domain(name="public", is_active=True)
        public_domain.allow_domain_requests = True
        public_domain.save()

        response = self.client.get(reverse("domain_homepage", args=[public_domain.name]), follow=True)
        self.assertEqual(response.status_code, 200)

        public_domain.delete()

    def test_disallow_domain_requests(self):
        self.client.login(username=self.username, password=self.password)

        private_domain = Domain(name="private", is_active=True)
        private_domain.save()

        response = self.client.get(reverse("domain_homepage", args=[private_domain.name]), follow=True)
        self.assertEqual(response.status_code, 404)

        private_domain.delete()

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

    def delete_domain_snapshots(self):
        for snap in self.domain.snapshots():
            snap.delete()

    @teardown(delete_domain_snapshots)
    def test_exchange_snapshot_view(self):
        """
        Tests creating a new exchange snapshot and then creating another snapshot
        """

        self.client.login(username=self.username, password=self.password)
        app_publish = "{}-publish".format(self.app._id)
        filename = 'file.txt'

        data = {
            'title': 'Title',
            'short_description': 'Description',
            'description': 'Description',
            'project_type': 'MCH',
            'license': 'cc',
            'documentation_file': SimpleUploadedFile(filename, b'contents'),
            'publish_on_submit': 'yes',
            'cda_confirmed': True,
            app_publish: True,
        }

        response = self.client.post(
            reverse(CreateNewExchangeSnapshotView.urlname, args=[self.domain.name]),
            data,
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        published = self.domain.published_snapshot()
        self.assertIsNotNone(published)

        self.assertEqual(published.title, data['title'])
        self.assertEqual(published.documentation_file_path, filename)

        # Should keep documentation file when old_documentation_file is specified
        del data['documentation_file']
        data['old_documentation_file'] = True

        response = self.client.post(
            reverse(CreateNewExchangeSnapshotView.urlname, args=[self.domain.name]),
            data,
            follow=True
        )
        self.domain = Domain.get(self.domain._id)
        self.assertEqual(response.status_code, 200)
        snapshots = list(self.domain.snapshots())
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[0].documentation_file_path, filename)
        self.assertEqual(snapshots[1].documentation_file_path, filename)


class BaseAutocompleteTest(TestCase):

    def verify(self, autocomplete_enabled, view_path, *fields):
        flag = not autocomplete_enabled
        setting_path = 'django.conf.settings.ENABLE_DRACONIAN_SECURITY_FEATURES'
        # HACK use patch to work around bug in override_settings
        # https://github.com/django-compressor/django-appconf/issues/30
        with patch(setting_path, flag):
            response = self.client.get(view_path)
            soup = BeautifulSoup(response.content)
            for field in fields:
                tag = soup.find("input", attrs={"name": field})
                self.assertTrue(tag, "field not found: " + field)
                print(tag)
                is_enabled = tag.get("autocomplete") != "off"
                self.assertEqual(is_enabled, autocomplete_enabled)


class TestPasswordResetFormAutocomplete(BaseAutocompleteTest):

    def test_autocomplete_enabled(self):
        self.verify(True, "/accounts/password_reset_email/", "email")

    def test_autocomplete_disabled(self):
        self.verify(False, "/accounts/password_reset_email/", "email")
