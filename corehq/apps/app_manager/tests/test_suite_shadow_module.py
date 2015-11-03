# -*- coding: utf-8 -*-
from django.test import SimpleTestCase
from corehq.apps.app_manager.models import Application
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
        app = Application.wrap(self.get_json('shadow_module_families'))
        (shadow, parent, child) = self._get_family_modules(app)
        shadow.source_module_id = parent.unique_id
        self.assertXmlEqual(self.get_xml('shadow_module_families_source_parent'), app.create_suite())

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
