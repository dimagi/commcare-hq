from django.utils.unittest.case import TestCase
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

    def _test_generic_suite(self, app_tag, suite_tag=None):
        suite_tag = suite_tag or app_tag
        app = Application.wrap(self.get_json(app_tag))
        self.assertXmlEqual(self.get_xml(suite_tag), app.create_suite())

    def test_normal_suite(self):
        self._test_generic_suite('app', 'normal-suite')

    def test_tiered_select(self):
        self._test_generic_suite('tiered-select', 'tiered-select')

    def test_3_tiered_select(self):
        self._test_generic_suite('tiered-select-3', 'tiered-select-3')

    def test_multisort_suite(self):
        self._test_generic_suite('multi-sort', 'multi-sort')

    def test_callcenter_suite(self):
        self._test_generic_suite('call-center')