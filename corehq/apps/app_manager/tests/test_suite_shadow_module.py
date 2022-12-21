from django.test import SimpleTestCase

from corehq.apps.app_manager.models import Application, Module, ShadowModule
from corehq.apps.app_manager.tests.util import patch_get_xform_resource_overrides, SuiteMixin, TestXmlMixin


@patch_get_xform_resource_overrides()
class ShadowModuleSuiteTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def test_shadow_module(self, *args):
        self._test_generic_suite('shadow_module')

    def test_shadow_module_forms_only(self, *args):
        self._test_generic_suite('shadow_module_forms_only')

    def test_shadow_module_cases(self, *args):
        self._test_generic_suite('shadow_module_cases')


@patch_get_xform_resource_overrides()
class ShadowModuleWithChildSuiteTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        self.app = Application.new_app('domain', "Untitled Application")

        self.parent = self.app.add_module(Module.new_module('Parent Module', None))
        self.app.new_form(self.parent.id, "Parent Form", None)

        self.child = self.app.add_module(Module.new_module('Child Module', None))
        self.child.root_module_id = self.parent.unique_id
        self.app.new_form(self.child.id, "Child Form", None)

        self.shadow = self.app.add_module(ShadowModule.new_module('Shadow Module', None))

    def test_shadow_module_source_parent_v1(self, *args):
        self.shadow.shadow_module_version = 1
        self.shadow.source_module_id = self.parent.unique_id
        # This is actually incorrect behaviour, but we keep this test around for backwards compatibility
        self.assertXmlPartialEqual(self.get_xml('shadow_module_families_source_parent_v1'),
                                   self.app.create_suite(), "./menu")

    def test_shadow_module_source_parent(self, *args):
        # With version 2 style shadow modules, we need a real module for the child
        self.shadow.source_module_id = self.parent.unique_id
        self.shadow_child = self.app.add_module(
            ShadowModule.new_module('Shadow Child Module', None)
        )
        self.shadow_child.source_module_id = self.child.unique_id
        self.shadow_child.root_module_id = self.shadow.unique_id
        self.assertXmlPartialEqual(self.get_xml('shadow_module_families_source_parent'),
                                   self.app.create_suite(), "./menu")

    def test_shadow_module_source_parent_forms_only_v1(self, *args):
        self.shadow.shadow_module_version = 1
        self.shadow.source_module_id = self.parent.unique_id
        for m in self.app.get_modules():
            m.put_in_root = True
        self.assertXmlPartialEqual(self.get_xml('shadow_module_families_source_parent_forms_only_v1'),
                                   self.app.create_suite(), "./menu")

    def test_shadow_module_source_parent_forms_only(self, *args):
        self.shadow.source_module_id = self.parent.unique_id
        self.shadow_child = self.app.add_module(ShadowModule.new_module('Shadow Child Module', None))
        self.shadow_child.source_module_id = self.child.unique_id
        self.shadow_child.root_module_id = self.shadow.unique_id
        for m in self.app.get_modules():
            m.put_in_root = True
        self.assertXmlPartialEqual(self.get_xml('shadow_module_families_source_parent_forms_only'),
                                   self.app.create_suite(), "./menu")

    def test_shadow_module_source_child(self, *args):
        self.shadow.source_module_id = self.child.unique_id
        self.assertXmlPartialEqual(self.get_xml('shadow_module_families_source_child'),
                                   self.app.create_suite(), "./menu")

    def test_mixture_v1_v2_shadow_modules(self, *args):
        """If there are both V1 and V2 shadow modules pointing to the same source, they
        should both be added to the suite with their different semantics to
        maintain backwards compatibility

        """
        self.shadow.shadow_module_version = 1
        self.shadow.source_module_id = self.parent.unique_id

        self.shadow_v2 = self.app.add_module(ShadowModule.new_module('V2 Shadow Module', None))
        self.shadow_v2.source_module_id = self.parent.unique_id
        self.shadow_child = self.app.add_module(
            ShadowModule.new_module('Shadow Child Module', None)
        )
        self.shadow_child.source_module_id = self.child.unique_id
        self.shadow_child.root_module_id = self.shadow_v2.unique_id

        self.assertXmlPartialEqual(self.get_xml('shadow_module_source_parent_v1_v2'),
                                   self.app.create_suite(), "./menu")


@patch_get_xform_resource_overrides()
class ShadowModuleWithPersistentCaseContextOnSource(SimpleTestCase, SuiteMixin):
    def setUp(self):
        self.app = Application.new_app('domain', "Untitled Application")
        self.parent = self.app.add_module(Module.new_module('Parent Module', None))
        self.parent.case_details.short.persist_case_context = True
        form = self.app.new_form(self.parent.id, "Parent Form", None)
        form.requires = 'case'
        self.shadow = self.app.add_module(ShadowModule.new_module('Shadow Module', None))

    def test_source_module_have_persistent_context_enabled(self, *args):
        """When a shadow module doesn't have persistent case context enabled, but its source module does, then the
        shadow module should not be regarded as also having this setting enabled. A KeyError will be raised if
        this happens, and this test will fail.
        """
        self.shadow.source_module_id = self.parent.unique_id
        self.app.create_suite()
