# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
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

    def _get_family_app(self):
        app = Application.new_app('domain', "Untitled Application")

        parent = app.add_module(Module.new_module('module', None))
        app.new_form(parent.id, "Untitled Form", None)

        child = app.add_module(Module.new_module('module', None))
        child.root_module_id = parent.unique_id

        app.new_form(child.id, "Untitled Form", None)
        shadow = app.add_module(ShadowModule.new_module('module', None))

        return (app, shadow)

    def test_shadow_module_source_parent(self):
        (app, shadow) = self._get_family_app()
        parent = [m for m in app.get_modules() if m.doc_type == 'Module' and m.root_module_id is None][0]
        shadow.source_module_id = parent.unique_id
        self.assertXmlPartialEqual(self.get_xml('shadow_module_families_source_parent'),
                                   app.create_suite(), "./menu")

    def test_shadow_module_source_parent_forms_only(self):
        (app, shadow) = self._get_family_app()
        parent = [m for m in app.get_modules() if m.doc_type == 'Module' and m.root_module_id is None][0]
        shadow.source_module_id = parent.unique_id
        for m in app.get_modules():
            m.put_in_root = True
        self.assertXmlPartialEqual(self.get_xml('shadow_module_families_source_parent_forms_only'),
                                   app.create_suite(), "./menu")

    def test_shadow_module_source_child(self):
        (app, shadow) = self._get_family_app()
        child = [m for m in app.get_modules() if m.doc_type == 'Module' and m.root_module_id is not None][0]
        shadow.source_module_id = child.unique_id
        self.assertXmlPartialEqual(self.get_xml('shadow_module_families_source_child'),
                                   app.create_suite(), "./menu")
