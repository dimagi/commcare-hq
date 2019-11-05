from django.test import SimpleTestCase

from mock import patch

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.util import TestXmlMixin


class DaysAgoMigrationTest(SimpleTestCase, TestXmlMixin):
    file_path = ['data']

    def setUp(self):
        self.app = Application.wrap(self.get_json('days_ago_migration'))

    @patch('corehq.apps.app_manager.suite_xml.post_process.resources.get_xform_overrides', return_value=[])
    def test_suite(self, *args):
        suiteB = self.app.create_suite()
        self.assertXmlEqual(self.get_xml('days_ago_suite'), suiteB)
