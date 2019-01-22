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


class ShadowModuleWithChildSuiteTest(SimpleTestCase, TestXmlMixin, SuiteMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        self.app = Application.new_app('domain', "Untitled Application")

        self.parent = self.app.add_module(Module.new_module('Parent Module', None))
        self.app.new_form(self.parent.id, "Parent Form", None)

        self.child = self.app.add_module(Module.new_module('Child Module', None))
        self.child.root_module_id = self.parent.unique_id
        self.app.new_form(self.child.id, "Child Form", None)

        self.shadow = self.app.add_module(ShadowModule.new_module('Shadow Module', None))

    def test_shadow_module_source_parent(self):
        self.shadow.source_module_id = self.parent.unique_id
        self.assertXmlPartialEqual(self.get_xml('shadow_module_families_source_parent'),
                                   self.app.create_suite(), "./menu")

    def test_shadow_module_source_parent_forms_only(self):
        self.shadow.source_module_id = self.parent.unique_id
        for m in self.app.get_modules():
            m.put_in_root = True
        self.assertXmlPartialEqual(self.get_xml('shadow_module_families_source_parent_forms_only'),
                                   self.app.create_suite(), "./menu")

    def test_shadow_module_source_child(self):
        self.shadow.source_module_id = self.child.unique_id
        self.assertXmlPartialEqual(self.get_xml('shadow_module_families_source_child'),
                                   self.app.create_suite(), "./menu")
