from __future__ import print_function, unicode_literals

from django.core.urlresolvers import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.client import Client

from corehq import toggles
from corehq.apps.users.models import WebUser
from corehq.apps.receiverwrapper.models import AppStructureRepeater
from corehq.apps.domain.models import Domain
from corehq.apps.app_manager.models import Application, APP_V1
from corehq.apps.domain.views import CreateNewExchangeSnapshotView

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

        self.app = Application.new_app(domain="fandago",
                                       name="cheeto",
                                       application_version=APP_V1)
        self.app.save()

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
