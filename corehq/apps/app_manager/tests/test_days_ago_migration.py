from django.test import TestCase
import os
import json
from corehq.apps.app_manager.models import Application
from casexml.apps.case.tests.util import check_xml_line_by_line


class DaysAgoMigrationTest(TestCase):

    def setUp(self):
        with open(os.path.join(os.path.dirname(__file__), "data", 'days_ago_migration.json')) as f:
            app_doc = json.load(f)
        self.app = Application.wrap(app_doc)

    def test_suite(self):

        with open(os.path.join(os.path.dirname(__file__), 'data', 'days_ago_suite.xml')) as f:
            suiteA = f.read()

        suiteB = self.app.create_suite()

        check_xml_line_by_line(self, suiteA, suiteB)