import json
import os
from django.test import TestCase, Client
from corehq import Domain
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests import add_build


class BrokenBuildTest(TestCase):
    def setUp(self):
        domain = 'apptest'
        self.domain = Domain.get_or_create_with_name(domain, is_active=True)
        self.cc_2_build = add_build(version='2.7.0', build_number=20655)
        with open(os.path.join(os.path.dirname(__file__), 'data', 'yesno.json')) as f:
            source = json.load(f)
        self.app = Application.wrap(source)
        self.app.domain = domain
        self.app.save()
        self.build = self.app.make_build()
        self.build.save(increment_version=False)

    def tearDown(self):
        self.app.delete()
        self.build.delete()
        self.cc_2_build.delete()
        self.domain.delete()

    def test_broken_build(self):
        client = Client()
        url = '/a/{domain}/apps/download/{build_id}/suite.xml'.format(
            domain=self.build.domain,
            build_id=self.build.get_id,
        )
        self.build = Application.get(self.build.get_id)
        self.assertEqual(self.build.build_broken, False)

        # delete the file and do it again, and assert the build is broken
        self.assertIn('files/suite.xml', self.build._attachments)
        self.build.delete_attachment('files/suite.xml')
        self.assertNotIn('files/suite.xml', self.build._attachments)

        self.build = Application.get(self.build.get_id)
        response = client.get(url)
        self.assertEqual(response.status_code, 404)
        self.build = Application.get(self.build.get_id)
        self.assertEqual(self.build.build_broken, True)
