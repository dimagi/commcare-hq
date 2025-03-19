from django.test import SimpleTestCase

from corehq.apps.app_manager.const import (
    AUTO_SELECT_CASE,
    AUTO_SELECT_RAW,
    WORKFLOW_FORM,
    WORKFLOW_MODULE,
    WORKFLOW_PARENT_MODULE,
    WORKFLOW_PREVIOUS,
    WORKFLOW_ROOT,
)
from corehq.apps.app_manager.exceptions import SuiteValidationError
from corehq.apps.app_manager.models import (
    CaseTileGroupConfig,
    FormDatum,
    FormLink,
)
from corehq.apps.app_manager.suite_xml.features.case_tiles import (
    CaseTileTemplates,
)
from corehq.apps.app_manager.suite_xml.post_process.workflow import (
    CommandId,
    _replace_session_references_in_stack,
)
from corehq.apps.app_manager.suite_xml.xml_models import StackDatum
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.test_suite_case_tiles import (
    add_columns_for_case_details,
)
from corehq.apps.app_manager.tests.util import (
    TestXmlMixin,
    patch_get_xform_resource_overrides,
)
from corehq.apps.app_manager.xpath import session_var


@patch_get_xform_resource_overrides()
class TestFormWorkflow(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'form_workflow')

    def test_basic_form(self, *args):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('m0', 'frog')
        m1, m1f0 = factory.new_basic_module('m1', 'frog')

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="(today() - dob) &lt; 7", form_id=m1f0.unique_id, form_module_id=m1.unique_id)
        ]
        self.assertXmlPartialEqual(self.get_xml('form_link_basic_form'), factory.app.create_suite(), "./entry[1]")

    def test_basic_form_legacy_form_link_data(self, *args):
        """Test that FormLink objects without the `form_module_id` field still work"""
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('m0', 'frog')
        m1, m1f0 = factory.new_basic_module('m1', 'frog')

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="(today() - dob) &lt; 7", form_id=m1f0.unique_id)
        ]
        self.assertXmlPartialEqual(self.get_xml('form_link_basic_form'), factory.app.create_suite(), "./entry[1]")

    def test_registration_module(self, *args):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('m0', 'frog')

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="(today() - dob) &lt; 7", module_unique_id=m0.unique_id)
        ]
        self.assertXmlPartialEqual(
            self.get_xml('form_link_registration_module'),
            factory.app.create_suite(),
            "./entry[1]"
        )

    def test_followup_module(self, *args):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('m0', 'frog')

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="(today() - dob) &lt; 7", module_unique_id=m0.unique_id)
        ]
        factory.form_requires_case(m0f0)
        self.assertXmlPartialEqual(
            self.get_xml('form_link_followup_module'),
            factory.app.create_suite(),
            "./entry[1]"
        )

    def test_with_case_management_both_update(self, *args):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('m0', 'frog')
        factory.form_requires_case(m0f0)
        m1, m1f0 = factory.new_basic_module('m1', 'frog')
        factory.form_requires_case(m1f0)

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="(today() - dob) > 7", form_id=m1f0.unique_id, form_module_id=m1.unique_id)
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_update_case'), factory.app.create_suite(), "./entry[1]")

    def test_with_case_management_create_update(self, *args):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('m0', 'frog')
        factory.form_opens_case(m0f0)
        m1, m1f0 = factory.new_basic_module('m1', 'frog')
        factory.form_requires_case(m1f0)

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath='true()', form_id=m1f0.unique_id, form_module_id=m1.unique_id)
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_create_update_case'),
                                   factory.app.create_suite(), "./entry[1]")

    def test_with_case_management_multiple_links(self, *args):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('m0', 'frog')
        factory.form_opens_case(m0f0)
        m1, m1f0 = factory.new_basic_module('m1', 'frog')
        factory.form_requires_case(m1f0)

        m1f1 = factory.new_form(m1)
        factory.form_opens_case(m1f1)

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="a = 1", form_id=m1f0.unique_id, form_module_id=m1.unique_id),
            FormLink(xpath="a = 2", form_id=m1f1.unique_id, form_module_id=m1.unique_id)
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_multiple'), factory.app.create_suite(), "./entry[1]")

    def test_link_to_child_module_form(self, *args):
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
            FormLink(xpath="true()", form_id=m1f0.unique_id, form_module_id=m1.unique_id),
        ]

        m1f0.post_form_workflow = WORKFLOW_FORM
        m1f0.form_links = [
            FormLink(xpath="true()", form_id=m2f0.unique_id, form_module_id=m2.unique_id),
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_tdh'), factory.app.create_suite(), "./entry")

    def test_link_to_module(self, *args):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('Update Stripes', 'stripes')
        factory.form_requires_case(m0f0)
        m1, m1f0 = factory.new_basic_module('Update Solids', 'solids')
        factory.form_requires_case(m1f0)
        m2, m2f0 = factory.new_basic_module('Close Stripes', 'stripes')
        factory.form_requires_case(m2f0)

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [FormLink(xpath="true()", module_unique_id=m0.unique_id)]
        self.assertXmlPartialEqual("""
            <partial>
                <stack>
                  <create if="true()">
                    <command value="'m0'"/>
                  </create>
                </stack>
            </partial>
        """, factory.app.create_suite(), "./entry[1]/stack")

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [FormLink(xpath="true()", module_unique_id=m1.unique_id)]
        self.assertXmlPartialEqual("""
            <partial>
                <stack>
                  <create if="true()">
                    <command value="'m1'"/>
                  </create>
                </stack>
            </partial>
        """, factory.app.create_suite(), "./entry[1]/stack")

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [FormLink(xpath="true()", module_unique_id=m2.unique_id)]
        self.assertXmlPartialEqual("""
            <partial>
                <stack>
                  <create if="true()">
                    <command value="'m2'"/>
                  </create>
                </stack>
            </partial>
        """, factory.app.create_suite(), "./entry[1]/stack")

    def test_link_to_child_module(self, *args):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('Register City', 'city')
        factory.form_opens_case(m0f0)
        m1, m1f0 = factory.new_basic_module('Update City', 'city')
        factory.form_requires_case(m1f0)
        m2, m2f0 = factory.new_basic_module('Update Person', 'person', parent_module=m1)
        factory.form_requires_case(m2f0)

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [FormLink(xpath="true()", module_unique_id=m2.unique_id)]
        self.assertXmlPartialEqual("""
            <partial>
                <stack>
                  <create if="true()">
                    <command value="'m1'"/>
                    <datum id="case_id" value="instance('commcaresession')/session/data/case_id"/>
                    <command value="'m2'"/>
                  </create>
                </stack>
            </partial>
        """, factory.app.create_suite(), "./entry[1]/stack")

    def test_link_between_child_modules(self, *args):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('Update City', 'city')
        factory.form_requires_case(m0f0)
        m1, m1f0 = factory.new_basic_module('Update Person', 'person', parent_module=m0)
        factory.form_requires_case(m1f0)
        m2, m2f0 = factory.new_basic_module('Close City', 'city')
        factory.form_requires_case(m2f0)
        m3, m3f0 = factory.new_basic_module('Close Person', 'person', parent_module=m2)
        factory.form_requires_case(m3f0)

        m1f0.post_form_workflow = WORKFLOW_FORM
        m1f0.form_links = [FormLink(xpath="true()", module_unique_id=m3.unique_id)]
        self.assertXmlPartialEqual("""
            <partial>
                <stack>
                  <create if="true()">
                    <command value="'m2'"/>
                    <datum id="case_id" value="instance('commcaresession')/session/data/case_id"/>
                    <command value="'m3'"/>
                  </create>
                </stack>
            </partial>
        """, factory.app.create_suite(), "./entry[2]/stack")

    def test_link_from_child_module(self, *args):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('Update City', 'city')
        factory.form_requires_case(m0f0)
        m1, m1f0 = factory.new_basic_module('Update Person', 'person', parent_module=m0)
        factory.form_requires_case(m1f0)
        m2, m2f0 = factory.new_basic_module('Update planet', 'planet')
        factory.form_requires_case(m2f0)

        m1f0.post_form_workflow = WORKFLOW_FORM
        m1f0.form_links = [FormLink(xpath="true()", module_unique_id=m2.unique_id)]
        self.assertXmlPartialEqual("""
            <partial>
                <stack>
                  <create if="true()">
                    <command value="'m2'"/>
                  </create>
                </stack>
            </partial>
        """, factory.app.create_suite(), "./entry[2]/stack")

    def test_manual_form_link(self, *args):
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
            FormLink(xpath="true()", form_id=m1f0.unique_id, form_module_id=m1.unique_id, datums=[
                FormDatum(name='case_id', xpath="instance('commcaresession')/session/data/case_id_new_child_0")
            ]),
        ]

        m1f0.post_form_workflow = WORKFLOW_FORM
        m1f0.form_links = [
            FormLink(xpath="true()", form_id=m2f0.unique_id, form_module_id=m2.unique_id, datums=[
                FormDatum(name='case_id', xpath="instance('commcaresession')/session/data/case_id"),
                FormDatum(name='case_id_load_visit_0',
                          xpath="instance('commcaresession')/session/data/case_id_new_visit_0"),
            ]),
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_tdh'), factory.app.create_suite(), "./entry")

    def test_manual_form_link_bad_datums(self, *args):
        factory = AppFactory(build_version='2.9.0')

        m0, m0f0 = factory.new_basic_module('child visit', 'child')
        factory.form_requires_case(m0f0)
        factory.form_opens_case(m0f0, case_type='visit', is_subcase=True)

        m1, m1f0 = factory.new_advanced_module('visit history', 'visit', parent_module=m0)
        factory.form_requires_case(m1f0, 'child')
        factory.form_requires_case(m1f0, 'visit', parent_case_type='child')

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="true()", form_id=m1f0.unique_id, form_module_id=m1.unique_id, datums=[
                FormDatum(name='case_id', xpath="instance('commcaresession')/session/data/case_id"),
                # There should be a case_id_load_visit_0 datum defined here
            ]),
        ]

        with self.assertRaises(SuiteValidationError) as e:
            factory.app.create_suite()
        self.assertIn("Unable to link form 'child visit form 0', missing "
                      "variable 'case_id_load_visit_0'", str(e.exception))

    def test_manual_datum_takes_precedence(self, *args):
        # This test is based on a real issue that occurred, where manually
        # specified datums were being replaced with datums from the target that
        # didn't require selection
        factory = AppFactory(build_version='2.9.0')

        m0, m0f0 = factory.new_basic_module('module0', 'parent')
        factory.form_requires_case(m0f0, 'parent')

        # Set up a module with grouped case tiles - that use case isn't important,
        # what matters is that this creates a datum that is autopopulated
        m1, m1f0 = factory.new_basic_module('module1', 'child', parent_module=m0)
        factory.form_requires_case(m1f0, 'parent')
        factory.form_requires_case(m1f0, 'child')
        m1.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        add_columns_for_case_details(m1)
        m1.case_details.short.case_tile_group = CaseTileGroupConfig(
            index_identifier="parent", header_rows=3)
        m1.assign_references()

        m2, m2f0 = factory.new_basic_module('module2', 'case')
        m2f0.post_form_workflow = WORKFLOW_FORM
        m2f0.form_links = [
            FormLink(xpath="true()", form_id=m1f0.unique_id, form_module_id=m1.unique_id, datums=[
                FormDatum(name='case_id', xpath="instance('commcaresession')/session/data/case_id"),
                FormDatum(name='case_id_child', xpath="instance('commcaresession')/session/data/case_id"),
                FormDatum(name='case_id_parent_ids', xpath="instance('commcaresession')/session/data/case_id"),
            ]),
        ]

        expected = """<partial>
            <stack>
                <create if="true()">
                <command value="'m0'"/>
                <datum id="case_id" value="instance('commcaresession')/session/data/case_id"/>
                <command value="'m1'"/>
                <datum id="case_id_child" value="instance('commcaresession')/session/data/case_id"/>
                <datum id="case_id_parent_ids" value="instance('commcaresession')/session/data/case_id"/>
                <command value="'m1-f0'"/>
                </create>
            </stack>
        </partial>"""
        self.assertXmlPartialEqual(expected, factory.app.create_suite(), "./entry[3]/stack")

    def test_manual_form_link_with_fallback(self, *args):
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
            FormLink(xpath="true()", form_id=m1f0.unique_id, form_module_id=m1.unique_id, datums=[
                FormDatum(name='case_id', xpath="instance('commcaresession')/session/data/case_id_new_child_0")
            ]),
        ]

        m1f0.post_form_workflow = WORKFLOW_FORM
        condition_for_xpath = "instance('casedb')/casedb/case[@case_id = " \
                              "instance('commcaresession')/session/data/case_id]/prop = 'value'"
        m1f0.form_links = [
            FormLink(xpath="true()", form_id=m2f0.unique_id, form_module_id=m2.unique_id, datums=[
                FormDatum(name='case_id', xpath="instance('commcaresession')/session/data/case_id"),
                FormDatum(name='case_id_load_visit_0',
                          xpath="instance('commcaresession')/session/data/case_id_new_visit_0"),
            ]),
            FormLink(xpath=condition_for_xpath, form_id=m2f0.unique_id, form_module_id=m2.unique_id, datums=[
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

    def test_reference_to_missing_session_variable_in_stack(self, *args):
        # http://manage.dimagi.com/default.asp?236750
        #
        # Stack create blocks do not update the session after each datum
        # so items put into the session in one step aren't available later steps
        #
        #    <datum id="case_id_A" value="instance('commcaresession')/session/data/case_id_new_A"/>
        # -  <datum id="case_id_B" value="instance('casedb')/casedb/case[
        #       @case_id=instance('commcaresession')/session/data/case_id_A]/index/host"/>
        # +  <datum id="case_id_B" value="instance('casedb')/casedb/case[
        #       @case_id=instance('commcaresession')/session/data/case_id_new_A]/index/host"/>
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
            FormLink(xpath="true()", form_id=m2f0.unique_id, form_module_id=m2.unique_id, datums=[
                FormDatum(name='case_id_load_episode_0',
                          xpath="instance('commcaresession')/session/data/case_id_new_episode_0")
            ]),
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_enikshay'), factory.app.create_suite(), "./entry")

    def test_return_to_parent_module(self, *args):
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

    def test_return_to_child_module(self, *args):
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

    def test_return_to_shadow_module(self, *args):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('enroll child', 'child')
        factory.form_requires_case(m0f0)
        m0f0.post_form_workflow = WORKFLOW_MODULE

        factory.new_shadow_module('shadow_module', m0, with_form=False)

        expected = """
        <partial>
            <stack>
              <create>
                <command value="'m1'"/>
              </create>
            </stack>
        </partial>
        """

        self.assertXmlPartialEqual(expected, factory.app.create_suite(), "./entry[2]/stack")

    def test_link_to_form_in_parent_module(self, *args):
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
            FormLink(xpath="true()", form_id=m1f0.unique_id, form_module_id=m1.unique_id),
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_child_modules'),
                                   factory.app.create_suite(), "./entry[3]")

    def test_form_links_submodule(self, *args):
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
            FormLink(xpath="true()", form_id=m1f1.unique_id, form_module_id=m1.unique_id),
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_submodule'), factory.app.create_suite(), "./entry")

    def test_form_links_within_shadow_module(self):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('parent', 'mother')
        factory.new_shadow_module('shadow_module', m0, with_form=False)

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [FormLink(xpath='true()', form_id=m0f0.unique_id, form_module_id=m0.unique_id)]

        suite_xml = factory.app.create_suite()

        # In m0, the regular module, EOF nav goes back to m0
        expected = """
        <partial>
            <stack>
                <create if="true()">
                    <command value="'m0'"/>
                    <command value="'m0-f0'"/>
                </create>
            </stack>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite_xml, "./entry[1]/stack")

        # In m1, the shadow module, EOF nav uses the shadow module
        expected = """
        <partial>
            <stack>
                <create if="true()">
                    <command value="'m1'"/>
                    <command value="'m1-f0'"/>
                </create>
            </stack>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite_xml, "./entry[2]/stack")

    def test_form_links_to_shadow_module(self):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('parent', 'mother')
        m1, m1f0 = factory.new_basic_module('other', 'mother')
        m2 = factory.new_shadow_module('shadow_module', m1, with_form=False)

        #link from m0-f0 to m1-f0 (in the shadow module)
        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [FormLink(xpath='true()', form_id=m1f0.unique_id, form_module_id=m2.unique_id)]

        suite_xml = factory.app.create_suite()

        # In m0, the regular module, EOF nav goes back to m0
        expected = """
        <partial>
            <stack>
                <create if="true()">
                    <command value="'m2'"/>
                    <command value="'m2-f0'"/>
                </create>
            </stack>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite_xml, "./entry[1]/stack")

    def test_form_links_other_child_module(self):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('parent', 'mother')
        factory.form_opens_case(m0f0)
        m1, m1f0 = factory.new_basic_module('child', 'baby', parent_module=m0)
        factory.form_requires_case(m1f0)

        m0f1 = factory.new_form(m0)
        m0f1.post_form_workflow = WORKFLOW_FORM
        m0f1.form_links = [FormLink(xpath='true()', form_id=m1f0.unique_id, form_module_id=m1.unique_id)]

        m2, m2f0 = factory.new_basic_module('other_module', 'baby')
        m2f0.post_form_workflow = WORKFLOW_FORM
        m2f0.form_links = [FormLink(xpath='true()', form_id=m1f0.unique_id, form_module_id=m1.unique_id)]
        suite_xml = factory.app.create_suite()

        # m0f1 links to m1f0, a form in its child module. Here's the stack for that:
        expected = """
        <partial>
            <stack>
                <create if="true()">
                    <command value="'m0'"/>
                    <command value="'m1'"/>
                    <datum id="case_id_new_mother_0" value="uuid()"/>
                    <datum id="case_id" value="instance('commcaresession')/session/data/case_id"/>
                    <command value="'m1-f0'"/>
                </create>
            </stack>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite_xml, "./entry[2]/stack")

        # m2f0 links to m1f0, a form in a separate child module, here's the stack there
        expected = """
        <partial>
            <stack>
                <create if="true()">
                    <command value="'m0'"/>
                    <command value="'m1'"/>
                    <datum id="case_id_new_mother_0" value="uuid()"/>
                    <datum id="case_id" value="instance('commcaresession')/session/data/case_id"/>
                    <command value="'m1-f0'"/>
                </create>
            </stack>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite_xml, "./entry[4]/stack")

    def test_form_links_other_child_module_manual_linking(self):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('parent', 'mother')
        factory.form_requires_case(m0f0)
        m1, m1f0 = factory.new_basic_module('child', 'baby', parent_module=m0)
        factory.form_requires_case(m1f0)

        m2, m2f0 = factory.new_basic_module('other_module', 'baby')
        factory.form_opens_case(m2f0, 'baby')
        m2f0.post_form_workflow = WORKFLOW_FORM
        m2f0.form_links = [FormLink(
            xpath='true()', form_id=m1f0.unique_id, form_module_id=m1.unique_id,
        )]
        suite_xml = factory.app.create_suite()

        # m2f0 links to m1f0 (child of m0-f0) - automatic linking
        expected = """
        <partial>
          <stack>
            <create if="true()">
              <command value="'m0'"/>
              <datum id="case_id" value="instance('commcaresession')/session/data/case_id"/>
              <command value="'m1'"/>
              <datum id="case_id_baby" value="instance('commcaresession')/session/data/case_id_new_baby_0"/>
              <command value="'m1-f0'"/>
            </create>
          </stack>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite_xml, "./entry[3]/stack")

        # set manual links
        m2f0.form_links = [FormLink(
            xpath='true()', form_id=m1f0.unique_id, form_module_id=m1.unique_id,
            datums=[
                FormDatum(name="case_id", xpath="xpath1"),
                FormDatum(name="case_id_baby", xpath="xpath2"),
            ]
        )]

        suite_xml = factory.app.create_suite()
        expected = """
        <partial>
          <stack>
            <create if="true()">
              <command value="'m0'"/>
              <datum id="case_id" value="xpath1"/>
              <command value="'m1'"/>
              <datum id="case_id_baby" value="xpath2"/>
              <command value="'m1-f0'"/>
            </create>
          </stack>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite_xml, "./entry[3]/stack")

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

        m6 = factory.new_shadow_module('shadow_module', m1, with_form=False)
        factory.new_shadow_module('shadow_child', m5, with_form=False, parent_module=m6)

        for module in factory.app.get_modules():
            for form in module.get_forms():
                form.post_form_workflow = mode

        return factory.app

    def test_form_workflow_previous(self, *args):
        app = self._build_workflow_app(WORKFLOW_PREVIOUS)
        self.assertXmlPartialEqual(self.get_xml('suite-workflow-previous'), app.create_suite(), "./entry")

    def test_form_workflow_module(self, *args):
        app = self._build_workflow_app(WORKFLOW_MODULE)
        self.assertXmlPartialEqual(self.get_xml('suite-workflow-module'), app.create_suite(), "./entry")

    def test_form_workflow_module_in_root(self, *args):
        app = self._build_workflow_app(WORKFLOW_PREVIOUS)
        for m in [1, 2]:
            module = app.get_module(m)
            module.put_in_root = True

        self.assertXmlPartialEqual(self.get_xml('suite-workflow-module-in-root'), app.create_suite(), "./entry")

    def test_form_workflow_root(self, *args):
        app = self._build_workflow_app(WORKFLOW_ROOT)
        self.assertXmlPartialEqual(self.get_xml('suite-workflow-root'), app.create_suite(), "./entry")


class TestReplaceSessionRefs(SimpleTestCase):
    def test_replace_session_references_in_stack(self):
        children = [
            CommandId('m0'),
            StackDatum(id='a', value=session_var('new_a')),
            StackDatum(id='b', value=session_var('new_b')),
            StackDatum(id='c', value=f"instance('casedb')/case/[@case_id = {session_var('a')}]/index/parent"),
            StackDatum(id='d', value=f"if({session_var('c')}, {session_var('c')}, {session_var('a')}]"),
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
