from django.test import TestCase

from corehq.apps.app_manager.exceptions import ResourceOverrideError
from corehq.apps.app_manager.suite_xml.post_process.resources import add_xform_overrides
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin


class SuiteResourceOverridesTest(TestCase, TestXmlMixin):
    file_path = ('data', 'suite')

    @classmethod
    def setUp(self):
        super().setUpClass()
        self.factory = AppFactory(build_version='2.40.0')
        module, form = self.factory.new_basic_module('module0', 'noun')
        self.factory.new_form(module)
        self.factory.new_form(module)
        self.factory.app.save()

    def test_overrides(self):
        forms = list(self.factory.app.get_module(0).get_forms())
        add_xform_overrides(self.factory.app.domain, self.factory.app.master_id, {
            forms[0].unique_id: '123',
            forms[1].unique_id: '456',
        })
        expected = """
            <partial>
              <xform>
                <resource descriptor="Form: (Module module0 module) - module0 form 0" id="{}" version="1">
                  <location authority="local">./modules-0/forms-0.xml</location>
                  <location authority="remote">./modules-0/forms-0.xml</location>
                </resource>
              </xform>
              <xform>
                <resource descriptor="Form: (Module module0 module) - module0 form 1" id="{}" version="1">
                  <location authority="local">./modules-0/forms-1.xml</location>
                  <location authority="remote">./modules-0/forms-1.xml</location>
                </resource>
              </xform>
              <xform>
                <resource descriptor="Form: (Module module0 module) - module0 form 2" id="{}" version="1">
                  <location authority="local">./modules-0/forms-2.xml</location>
                  <location authority="remote">./modules-0/forms-2.xml</location>
                </resource>
              </xform>
            </partial>
        """.format('123', '456', forms[2].unique_id)
        self.assertXmlPartialEqual(expected, self.factory.app.create_suite(), "./xform")

    def test_duplicate_overrides_raises(self):
        forms = list(self.factory.app.get_module(0).get_forms())
        add_xform_overrides(self.factory.app.domain, self.factory.app.master_id, {
            forms[0].unique_id: '123',
            forms[1].unique_id: '456',
            forms[2].unique_id: '456',
        })
        with self.assertRaises(ResourceOverrideError):
            self.factory.app.create_suite()
