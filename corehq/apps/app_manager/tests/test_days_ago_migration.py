from django.test import SimpleTestCase

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.util import TestXmlMixin, patch_get_xform_resource_overrides


class DaysAgoMigrationTest(SimpleTestCase, TestXmlMixin):
    file_path = ['data']

    def setUp(self):
        self.app = Application.wrap(self.get_json('days_ago_migration'))

    @patch_get_xform_resource_overrides()
    def test_suite(self, *args):
        suiteB = self.app.create_suite()
        self.assertXmlEqual(self.get_xml('days_ago_suite'), suiteB)
