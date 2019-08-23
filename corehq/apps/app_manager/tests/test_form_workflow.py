from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase

from corehq.apps.app_manager.const import (
    AUTO_SELECT_RAW,
    AUTO_SELECT_CASE,
    WORKFLOW_FORM,
    WORKFLOW_MODULE,
    WORKFLOW_PREVIOUS,
    WORKFLOW_ROOT,
    WORKFLOW_PARENT_MODULE,
)
from corehq.apps.app_manager.models import FormDatum, FormLink
from corehq.apps.app_manager.suite_xml.post_process.workflow import _replace_session_references_in_stack, CommandId
from corehq.apps.app_manager.suite_xml.xml_models import StackDatum
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.app_manager.xpath import session_var


class TestFormWorkflow(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'form_workflow')

    def test_basic(self):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('m0', 'frog')
        m1, m1f0 = factory.new_basic_module('m1', 'frog')

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="(today() - dob) &lt; 7", form_id=m1f0.unique_id)
        ]
        self.assertXmlPartialEqual(self.get_xml('form_link_basic'), factory.app.create_suite(), "./entry[1]")

    def test_with_case_management_both_update(self):
        factory = AppFactory(build_version='2.9.0')
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
        factory = AppFactory(build_version='2.9.0')
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
        factory = AppFactory(build_version='2.9.0')
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
        factory = AppFactory(build_version='2.9.0')
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

    def test_manual_form_link(self):
        factory = AppFactory(build_version='2.9.0')
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
            FormLink(xpath="true()", form_id=m1f0.unique_id, datums=[
                FormDatum(name='case_id', xpath="instance('commcaresession')/session/data/case_id_new_child_0")
            ]),
        ]

        m1f0.post_form_workflow = WORKFLOW_FORM
        m1f0.form_links = [
            FormLink(xpath="true()", form_id=m2f0.unique_id, datums=[
                FormDatum(name='case_id', xpath="instance('commcaresession')/session/data/case_id"),
                FormDatum(name='case_id_load_visit_0', xpath="instance('commcaresession')/session/data/case_id_new_visit_0"),
            ]),
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_tdh'), factory.app.create_suite(), "./entry")

    def test_manual_form_link_with_fallback(self):
        factory = AppFactory(build_version='2.9.0')
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
            FormLink(xpath="true()", form_id=m1f0.unique_id, datums=[
                FormDatum(name='case_id', xpath="instance('commcaresession')/session/data/case_id_new_child_0")
            ]),
        ]

        m1f0.post_form_workflow = WORKFLOW_FORM
        condition_for_xpath = "instance('casedb')/casedb/case[@case_id = " \
                              "instance('commcaresession')/session/data/case_id]/prop = 'value'"
        m1f0.form_links = [
            FormLink(xpath="true()", form_id=m2f0.unique_id, datums=[
                FormDatum(name='case_id', xpath="instance('commcaresession')/session/data/case_id"),
                FormDatum(name='case_id_load_visit_0',
                          xpath="instance('commcaresession')/session/data/case_id_new_visit_0"),
            ]),
            FormLink(xpath=condition_for_xpath, form_id=m2f0.unique_id, datums=[
                FormDatum(name='case_id', xpath="instance('commcaresession')/session/data/case_id"),
                FormDatum(name='case_id_load_visit_0',
                          xpath="instance('commcaresession')/session/data/case_id_new_visit_0"),
            ]),
        ]

        m1f0.post_form_workflow_fallback = WORKFLOW_PREVIOUS
        self.assertXmlPartialEqual(self.get_xml('form_link_tdh_with_fallback_previous'),
                                   factory.app.create_suite(), "./entry")

        m1f0.post_form_workflow_fallback = WORKFLOW_MODULE
        self.assertXmlPartialEqual(self.get_xml('form_link_tdh_with_fallback_module'),
                                   factory.app.create_suite(), "./entry")

        m1f0.post_form_workflow_fallback = WORKFLOW_ROOT
        self.assertXmlPartialEqual(self.get_xml('form_link_tdh_with_fallback_root'),
                                   factory.app.create_suite(), "./entry")

    def test_reference_to_missing_session_variable_in_stack(self):
        # http://manage.dimagi.com/default.asp?236750
        #
        # Stack create blocks do not update the session after each datum
        # so items put into the session in one step aren't available later steps
        #
        #    <datum id="case_id_A" value="instance('commcaresession')/session/data/case_id_new_A"/>
        # -  <datum id="case_id_B" value="instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id_A]/index/host"/>
        # +  <datum id="case_id_B" value="instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id_new_A]/index/host"/>
        #
        # in the above example ``case_id_A`` is being added to the session and then
        # later referenced. However since the session doesn't get updated
        # the value isn't available in the session.
        #
        # To fix this we need to replace any references to previous variables with the full xpath which
        # that session variable references.
        #
        # See corehq.apps.app_manager.suite_xml.post_process.workflow._replace_session_references_in_stack

        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('person registration', 'person')
        factory.form_opens_case(m0f0)

        m1, m1f0 = factory.new_advanced_module('episode registration', 'episode')
        factory.form_requires_case(m1f0, case_type='person')
        factory.form_opens_case(m1f0, case_type='episode', is_subcase=True, is_extension=True)

        m2, m2f0 = factory.new_advanced_module('tests', 'episode')
        factory.form_requires_case(m2f0, 'episode')
        factory.advanced_form_autoloads(m2f0, AUTO_SELECT_CASE, 'host', 'load_episode_0')

        m1f0.post_form_workflow = WORKFLOW_FORM
        m1f0.form_links = [
            FormLink(xpath="true()", form_id=m2f0.unique_id, datums=[
                FormDatum(name='case_id_load_episode_0', xpath="instance('commcaresession')/session/data/case_id_new_episode_0")
            ]),
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_enikshay'), factory.app.create_suite(), "./entry")

    def test_return_to_parent_module(self):
        factory = AppFactory(build_version='2.9.0')
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
        factory = AppFactory(build_version='2.9.0')
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
              </create>
            </stack>
        </partial>
        """

        self.assertXmlPartialEqual(expected, factory.app.create_suite(), "./entry[3]/stack")

    def test_link_to_form_in_parent_module(self):
        factory = AppFactory(build_version='2.9.0')
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

    def test_form_links_submodule(self):
        # Test that when linking between two forms in a submodule we match up the
        # session variables between the source and target form correctly
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('child visit', 'child')
        factory.form_requires_case(m0f0)
        factory.form_opens_case(m0f0, 'visit', is_subcase=True)

        m1, m1f0 = factory.new_advanced_module('visit histroy', 'visit', parent_module=m0)
        factory.form_requires_case(m1f0, 'child')
        factory.form_requires_case(m1f0, 'visit', parent_case_type='child')

        m1f1 = factory.new_form(m1)
        factory.form_requires_case(m1f1, 'child')
        factory.form_requires_case(m1f1, 'visit', parent_case_type='child')

        m1f0.post_form_workflow = WORKFLOW_FORM
        m1f0.form_links = [
            FormLink(xpath="true()", form_id=m1f1.unique_id),
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_submodule'), factory.app.create_suite(), "./entry")

    def _build_workflow_app(self, mode):
        factory = AppFactory(build_version='2.9.0')
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

        m5, m5f0 = factory.new_basic_module('m5', 'patient', parent_module=m1)
        factory.form_requires_case(m5f0)

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


class TestReplaceSessionRefs(SimpleTestCase):
    def test_replace_session_references_in_stack(self):
        children = [
            CommandId('m0'),
            StackDatum(id='a', value=session_var('new_a')),
            StackDatum(id='b', value=session_var('new_b')),
            StackDatum(id='c', value="instance('casedb')/case/[@case_id = {a}]/index/parent".format(a=session_var('a'))),
            StackDatum(id='d', value="if({c}, {c}, {a}]".format(a=session_var('a'), c=session_var('c')))
        ]

        clean = _replace_session_references_in_stack(children)
        clean_raw = []
        for child in clean:
            if isinstance(child, CommandId):
                clean_raw.append(child.id)
            else:
                clean_raw.append((child.id, child.value))

        new_c = "instance('casedb')/case/[@case_id = {a}]/index/parent".format(a=session_var('new_a'))
        self.assertEqual(clean_raw, [
            'm0',
            ('a', session_var('new_a')),
            ('b', session_var('new_b')),
            ('c', new_c),
            ('d', "if({c}, {c}, {a}]".format(a=session_var('new_a'), c=new_c))

        ])
