from django.utils.unittest.case import TestCase
from casexml.apps.case.tests import check_xml_line_by_line
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.util import TestFileMixin

class SuiteTest(TestCase, TestFileMixin):
    file_path = ('data', 'suite')
    def setUp(self):
        self.app = Application.wrap(self.get_json('app'))

    def test_normal_suite(self):
        check_xml_line_by_line(self, self.get_xml('normal-suite'), self.app.create_suite())
