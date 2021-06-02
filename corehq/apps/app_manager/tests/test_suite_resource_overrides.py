from django.test import TestCase

from corehq.apps.app_manager.exceptions import ResourceOverrideError
from corehq.apps.app_manager.suite_xml.post_process.resources import (
    add_xform_resource_overrides,
    get_xform_resource_overrides,
    copy_xform_resource_overrides,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin


class SuiteResourceOverridesTest(TestCase, TestXmlMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        super().setUp()
        self.factory = AppFactory(build_version='2.40.0')
        module, form = self.factory.new_basic_module('module0', 'noun')
        self.factory.new_form(module)
        self.factory.new_form(module)
        self.factory.app.save()

    def test_overrides(self):
        forms = list(self.factory.app.get_module(0).get_forms())
        add_xform_resource_overrides(self.factory.app.domain, self.factory.app.origin_id, {
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
        add_xform_resource_overrides(self.factory.app.domain, self.factory.app.origin_id, {
            forms[0].unique_id: '123',
            forms[1].unique_id: '456',
            forms[2].unique_id: '456',
        })
        with self.assertRaises(ResourceOverrideError):
            self.factory.app.create_suite()

    def test_copy_xform_resource_overrides(self):
        forms = list(self.factory.app.get_module(0).get_forms())
        add_xform_resource_overrides(self.factory.app.domain, self.factory.app.origin_id, {
            forms[0].unique_id: '123',
            forms[1].unique_id: '456',
        })

        copy_xform_resource_overrides(self.factory.app.domain, self.factory.app.origin_id, {
            forms[0].unique_id: '321',
            '123': '987',
        })

        overrides = get_xform_resource_overrides(self.factory.app.domain, self.factory.app.origin_id)
        self.assertEqual({o.pre_id: o.post_id for o in overrides.values()}, {
            forms[0].unique_id: '123',
            forms[1].unique_id: '456',
            '321': '123',
        })
