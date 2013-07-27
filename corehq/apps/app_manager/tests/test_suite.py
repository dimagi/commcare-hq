from django.utils.unittest.case import TestCase
from casexml.apps.case.tests import check_xml_line_by_line
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.util import TestFileMixin


# snippet from http://stackoverflow.com/questions/321795/comparing-xml-in-a-unit-test-in-python/7060342#7060342
from doctest import Example
from lxml.doctestcompare import LXMLOutputChecker

class XmlTest(TestCase):

    def assertXmlEqual(self, want, got):
        checker = LXMLOutputChecker()
        if not checker.check_output(want, got, 0):
            message = checker.output_difference(Example("", want), got, 0)
            raise AssertionError(message)
# end snippet

class SuiteTest(XmlTest, TestFileMixin):
    file_path = ('data', 'suite')
    def setUp(self):
        self.app = Application.wrap(self.get_json('app'))

    def test_normal_suite(self):
        self.assertXmlEqual(self.get_xml('normal-suite'), self.app.create_suite())
