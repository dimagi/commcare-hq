from django.test import SimpleTestCase

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin


class SuiteResourceOverridesTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'suite')

    @classmethod
    def setUpClass(cls):
        super(TestRemoveMedia, cls).setUpClass()
        self.factory = AppFactory(build_version='2.40.0')
        module = factory.new_basic_module('module0', 'noun')
        factory.new_form(module)
        factory.new_form(module)

    def test_overrides(self):
        expected = """
            <partial>
              TODO
            </partial>
        """
        self.assertXmlPartialEqual(expected, self.factory.app.create_suite(), "./xform")
