from django.test import SimpleTestCase
from corehq.apps.app_manager.models import (
    FormLink,
    WORKFLOW_FORM,
    WORKFLOW_MODULE,
    WORKFLOW_PREVIOUS,
    WORKFLOW_ROOT,
    WORKFLOW_PARENT_MODULE)
from corehq.apps.app_manager.const import AUTO_SELECT_RAW
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.feature_previews import MODULE_FILTER
from corehq.toggles import NAMESPACE_DOMAIN
from toggle.shortcuts import update_toggle_cache, clear_toggle_cache


class TestFormWorkflow(SimpleTestCase, TestFileMixin):
    file_path = ('data', 'form_workflow')

    def setUp(self):
        update_toggle_cache(MODULE_FILTER.slug, 'domain', True, NAMESPACE_DOMAIN)

    def tearDown(self):
        clear_toggle_cache(MODULE_FILTER.slug, 'domain', NAMESPACE_DOMAIN)

    def test_basic(self):
        factory = AppFactory(build_version='2.9.0/latest')
        m0, m0f0 = factory.new_basic_module('m0', 'frog')
        m1, m1f0 = factory.new_basic_module('m1', 'frog')

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="(today() - dob) &lt; 7", form_id=m1f0.unique_id)
        ]
        self.assertXmlPartialEqual(self.get_xml('form_link_basic'), factory.app.create_suite(), "./entry[1]")

    def test_with_case_management_both_update(self):
        factory = AppFactory(build_version='2.9.0/latest')
        m0, m0f0 = factory.new_basic_module('m0', 'frog')
        factory.form_requires_case(m0f0)
        m1, m1f0 = factory.new_basic_module('m1', 'frog')
        factory.form_requires_case(m1f0)

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="(today() - dob) > 7", form_id=m1f0.unique_id)
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_update_case'), factory.app.create_suite(), "./entry[1]")

    def test_with_case_management_create_update(self):
        factory = AppFactory(build_version='2.9.0/latest')
        m0, m0f0 = factory.new_basic_module('m0', 'frog')
        factory.form_opens_case(m0f0)
        m1, m1f0 = factory.new_basic_module('m1', 'frog')
        factory.form_requires_case(m1f0)

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath='true()', form_id=m1f0.unique_id)
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_create_update_case'), factory.app.create_suite(), "./entry[1]")

    def test_with_case_management_multiple_links(self):
        factory = AppFactory(build_version='2.9.0/latest')
        m0, m0f0 = factory.new_basic_module('m0', 'frog')
        factory.form_opens_case(m0f0)
        m1, m1f0 = factory.new_basic_module('m1', 'frog')
        factory.form_requires_case(m1f0)

        m1f1 = factory.new_form(m1)
        factory.form_opens_case(m1f1)

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="a = 1", form_id=m1f0.unique_id),
            FormLink(xpath="a = 2", form_id=m1f1.unique_id)
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_multiple'), factory.app.create_suite(), "./entry[1]")

    def test_link_to_child_module(self):
        factory = AppFactory(build_version='2.9.0/latest')
        m0, m0f0 = factory.new_basic_module('enroll child', 'child')
        factory.form_opens_case(m0f0)

        m1, m1f0 = factory.new_basic_module('child visit', 'child')
        factory.form_requires_case(m1f0)
        factory.form_opens_case(m1f0, case_type='visit', is_subcase=True)

        m2, m2f0 = factory.new_advanced_module('visit history', 'visit', parent_module=m1)
        factory.form_requires_case(m2f0, 'child')
        factory.form_requires_case(m2f0, 'visit', parent_case_type='child')

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="true()", form_id=m1f0.unique_id),
        ]

        m1f0.post_form_workflow = WORKFLOW_FORM
        m1f0.form_links = [
            FormLink(xpath="true()", form_id=m2f0.unique_id),
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_tdh'), factory.app.create_suite(), "./entry")

    def test_return_to_parent_module(self):
        factory = AppFactory(build_version='2.9.0/latest')
        m0, m0f0 = factory.new_basic_module('enroll child', 'child')
        factory.form_opens_case(m0f0)

        m1, m1f0 = factory.new_basic_module('child visit', 'child')
        factory.form_requires_case(m1f0)
        factory.form_opens_case(m1f0, case_type='visit', is_subcase=True)

        m2, m2f0 = factory.new_advanced_module('visit history', 'visit', parent_module=m1)
        factory.form_requires_case(m2f0, 'child')
        factory.form_requires_case(m2f0, 'visit', parent_case_type='child')

        m2f0.post_form_workflow = WORKFLOW_PARENT_MODULE

        expected = """
        <partial>
            <stack>
              <create>
                <command value="'m1'"/>
                <datum id="case_id" value="instance('commcaresession')/session/data/case_id"/>
                <datum id="case_id_new_visit_0" value="uuid()"/>
              </create>
            </stack>
        </partial>
        """

        self.assertXmlPartialEqual(expected, factory.app.create_suite(), "./entry[3]/stack")

    def test_return_to_child_module(self):
        factory = AppFactory(build_version='2.9.0/latest')
        m0, m0f0 = factory.new_basic_module('enroll child', 'child')
        factory.form_opens_case(m0f0)

        m1, m1f0 = factory.new_basic_module('child visit', 'child')
        factory.form_requires_case(m1f0)
        factory.form_opens_case(m1f0, case_type='visit', is_subcase=True)

        m2, m2f0 = factory.new_advanced_module('visit history', 'visit', parent_module=m1)
        factory.form_requires_case(m2f0, 'child')
        factory.form_requires_case(m2f0, 'visit', parent_case_type='child')

        m2f0.post_form_workflow = WORKFLOW_MODULE

        expected = """
        <partial>
            <stack>
              <create>
                <command value="'m1'"/>
                <datum id="case_id" value="instance('commcaresession')/session/data/case_id"/>
                <datum id="case_id_new_visit_0" value="uuid()"/>
                <command value="'m2'"/>
                <datum id="case_id_load_visit_0" value="instance('commcaresession')/session/data/case_id_load_visit_0"/>
              </create>
            </stack>
        </partial>
        """

        self.assertXmlPartialEqual(expected, factory.app.create_suite(), "./entry[3]/stack")

    def test_link_to_form_in_parent_module(self):
        factory = AppFactory(build_version='2.9.0/latest')
        m0, m0f0 = factory.new_basic_module('enroll child', 'child')
        factory.form_opens_case(m0f0)

        m1, m1f0 = factory.new_basic_module('child visit', 'child')
        factory.form_requires_case(m1f0)

        m2, m2f0 = factory.new_advanced_module('visit history', 'visit', parent_module=m1)
        factory.form_requires_case(m2f0, 'child')

        # link to child -> edit child
        m2f0.post_form_workflow = WORKFLOW_FORM
        m2f0.form_links = [
            FormLink(xpath="true()", form_id=m1f0.unique_id),
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_child_modules'), factory.app.create_suite(), "./entry[3]")

    def _build_workflow_app(self, mode):
        factory = AppFactory(build_version='2.9.0/latest')
        m0, m0f0 = factory.new_basic_module('m0', '')
        factory.new_form(m0)

        m1, m1f0 = factory.new_basic_module('m1', 'patient')
        m1f1 = factory.new_form(m1)
        factory.form_opens_case(m1f0)
        factory.form_requires_case(m1f1)

        m2, m2f0 = factory.new_basic_module('m2', 'patient')
        m2f1 = factory.new_form(m2)
        factory.form_requires_case(m2f0)
        factory.form_requires_case(m2f1)

        m3, m3f0 = factory.new_basic_module('m3', 'child')
        m3f1 = factory.new_form(m3)
        factory.form_requires_case(m3f0, parent_case_type='patient')
        factory.form_requires_case(m3f1)

        m4, m4f0 = factory.new_advanced_module('m4', 'patient')
        factory.form_requires_case(m4f0, case_type='patient')
        factory.form_requires_case(m4f0, case_type='patient')

        m4f1 = factory.new_form(m4)
        factory.form_requires_case(m4f1, case_type='patient')
        factory.form_requires_case(m4f1, case_type='patient')
        factory.form_requires_case(m4f1, case_type='patient')

        m4f2 = factory.new_form(m4)
        factory.form_requires_case(m4f2, case_type='patient')
        factory.form_requires_case(m4f2, case_type='patient')
        factory.advanced_form_autoloads(m4f2, AUTO_SELECT_RAW, 'case_id')
        for module in factory.app.get_modules():
            for form in module.get_forms():
                form.post_form_workflow = mode

        return factory.app

    def test_form_workflow_previous(self):
        app = self._build_workflow_app(WORKFLOW_PREVIOUS)
        self.assertXmlPartialEqual(self.get_xml('suite-workflow-previous'), app.create_suite(), "./entry")

    def test_form_workflow_module(self):
        app = self._build_workflow_app(WORKFLOW_MODULE)
        self.assertXmlPartialEqual(self.get_xml('suite-workflow-module'), app.create_suite(), "./entry")

    def test_form_workflow_module_in_root(self):
        app = self._build_workflow_app(WORKFLOW_PREVIOUS)
        for m in [1, 2]:
            module = app.get_module(m)
            module.put_in_root = True

        self.assertXmlPartialEqual(self.get_xml('suite-workflow-module-in-root'), app.create_suite(), "./entry")

    def test_form_workflow_root(self):
        app = self._build_workflow_app(WORKFLOW_ROOT)
        self.assertXmlPartialEqual(self.get_xml('suite-workflow-root'), app.create_suite(), "./entry")
