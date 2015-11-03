# -*- coding: utf-8 -*-
from django.test import SimpleTestCase
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module, ShadowModule
from corehq.apps.app_manager.tests.util import SuiteMixin, TestXmlMixin

class ShadowModuleSuiteTest(SimpleTestCase, TestXmlMixin, SuiteMixin):
    file_path = ('data', 'suite')

    def test_shadow_module(self):
        self._test_generic_suite('shadow_module')

    def test_shadow_module_forms_only(self):
        self._test_generic_suite('shadow_module_forms_only')

    def test_shadow_module_cases(self):
        self._test_generic_suite('shadow_module_cases')

    def _get_family_modules(self, app):
        # TODO: create app programatically instead of pulling from json
        return (
            [m for m in app.get_modules() if m.doc_type == 'ShadowModule'][0],
            [m for m in app.get_modules() if m.doc_type == 'Module' and m.root_module_id is None][0],
            [m for m in app.get_modules() if m.doc_type == 'Module' and m.root_module_id is not None][0],
        )

    def test_shadow_module_source_parent(self):
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)
        parent = app.add_module(Module.new_module('module', None))
        app.new_form(parent.id, "Untitled Form", None)
        child = app.add_module(Module.new_module('module', None))
        child.root_module_id = parent.unique_id
        app.new_form(child.id, "Untitled Form", None)
        shadow = app.add_module(ShadowModule.new_module('module', None))

        shadow.source_module_id = parent.unique_id
        self.assertXmlPartialEqual(self.get_xml('shadow_module_families_source_parent'), app.create_suite(), "./menu")

    def test_shadow_module_source_parent_forms_only(self):
        app = Application.wrap(self.get_json('shadow_module_families'))
        (shadow, parent, child) = self._get_family_modules(app)
        shadow.source_module_id = parent.unique_id
        shadow.put_in_root = True
        parent.put_in_root = True
        child.put_in_root = True
        self.assertXmlEqual(self.get_xml('shadow_module_families_source_parent_forms_only'), app.create_suite())

    def test_shadow_module_source_child(self):
        app = Application.wrap(self.get_json('shadow_module_families'))
        (shadow, parent, child) = self._get_family_modules(app)
        shadow.source_module_id = child.unique_id
        self.assertXmlEqual(self.get_xml('shadow_module_families_source_child'), app.create_suite())
