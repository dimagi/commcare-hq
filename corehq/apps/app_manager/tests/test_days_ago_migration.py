from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.util import TestXmlMixin
from django.test import SimpleTestCase


class DaysAgoMigrationTest(SimpleTestCase, TestXmlMixin):
    file_path = ['data']

    def setUp(self):
        self.app = Application.wrap(self.get_json('days_ago_migration'))

    def test_suite(self):
        suiteB = self.app.create_suite()
        self.assertXmlEqual(self.get_xml('days_ago_suite'), suiteB)
