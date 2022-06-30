from django.test import SimpleTestCase

from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    TestXmlMixin,
    patch_get_xform_resource_overrides,
)


@patch_get_xform_resource_overrides()
class SuiteFilterTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def test_form_filter(self, *args):
        """
        Ensure form filter gets added correctly and appropriate instances get added to the entry.
        """
        app = Application.wrap(self.get_json('suite-advanced'))
        form = app.get_module(1).get_form(1)
        form.form_filter = "./edd = '123'"

        expected = """
        <partial>
          <menu id="m1">
            <text>
              <locale id="modules.m1"/>
            </text>
            <command id="m1-f0"/>
            <command id="m1-f1" relevant="instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id_load_clinic0]/edd = '123'"/>
            <command id="m1-f2"/>
            <command id="m1-case-list"/>
          </menu>
        </partial>
        """
        self.assertXmlPartialEqual(expected, app.create_suite(), "./menu[@id='m1']")

    def test_module_filter(self, *args):
        """
        Ensure module filter gets added correctly
        """
        app = Application.new_app('domain', "Untitled Application")
        app.build_spec.version = '2.20.0'
        module = app.add_module(Module.new_module('m0', None))
        module.new_form('f0', None)

        module.module_filter = "/mod/filter = '123'"
        self.assertXmlPartialEqual(
            self.get_xml('module-filter'),
            app.create_suite(),
            "./menu[@id='m0']"
        )

    def test_module_filter_with_session(self, *args):
        app = Application.new_app('domain', "Untitled Application")
        app.build_spec.version = '2.20.0'
        module = app.add_module(Module.new_module('m0', None))
        form = module.new_form('f0', None)
        form.xmlns = 'f0-xmlns'

        module.module_filter = "#session/user/mod/filter = '123'"
        self.assertXmlPartialEqual(
            self.get_xml('module-filter-user'),
            app.create_suite(),
            "./menu[@id='m0']"
        )
        self.assertXmlPartialEqual(
            self.get_xml('module-filter-user-entry'),
            app.create_suite(),
            "./entry[1]"
        )
