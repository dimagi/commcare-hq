from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.util import TestFileMixin
from django.test import SimpleTestCase as TestCase


class DaysAgoMigrationTest(TestCase, TestFileMixin):
    file_path = ['data']

    def setUp(self):
        self.app = Application.wrap(self.get_json('days_ago_migration'))

    def test_suite(self):
        suiteB = self.app.create_suite()
        self.assertXmlEqual(self.get_xml('days_ago_suite'), suiteB)