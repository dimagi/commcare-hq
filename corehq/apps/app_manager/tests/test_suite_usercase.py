from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    Application,
    ConditionalCaseUpdate,
    Module,
    PreloadAction,
    UpdateCaseAction,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    TestXmlMixin,
    patch_get_xform_resource_overrides,
)


@patch_get_xform_resource_overrides()
class SuiteUsercaseTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def test_usercase_id_added_update(self, *args):
        app = Application.new_app('domain', "Untitled Application")

        module = app.add_module(Module.new_module("Untitled Module", None))
        module.case_type = 'child'

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://id_m1-f0'
        form.requires = 'case'
        form.actions.usercase_update = UpdateCaseAction(
            update={'name': ConditionalCaseUpdate(question_path='/data/question1')})
        form.actions.usercase_update.condition.type = 'always'

        self.assertXmlPartialEqual(self.get_xml('usercase_entry'), app.create_suite(), "./entry[1]")

    def test_usercase_id_added_preload(self, *args):
        app = Application.new_app('domain', "Untitled Application")

        module = app.add_module(Module.new_module("Untitled Module", None))
        module.case_type = 'child'

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://id_m1-f0'
        form.requires = 'case'
        form.actions.usercase_preload = PreloadAction(preload={'/data/question1': 'name'})
        form.actions.usercase_preload.condition.type = 'always'

        self.assertXmlPartialEqual(self.get_xml('usercase_entry'), app.create_suite(), "./entry[1]")

    def test_usercase_assertion_added_in_child_module(self, *args):
        factory = AppFactory()

        m0, m0f0 = factory.new_basic_module("parent", "parent")
        factory.form_requires_case(m0f0, "parent")
        factory.form_uses_usercase(m0f0, {"name": ConditionalCaseUpdate(question_path='/data/question1')})

        m1, m1f0 = factory.new_basic_module("child", "child", parent_module=m0)
        factory.form_requires_case(m1f0, "child", parent_case_type="parent")

        expected = """
        <partial>
          <entry>
            <command id="m1-f0">
              <text>
                <locale id="forms.m1f0"/>
              </text>
            </command>
            <instance id="casedb" src="jr://instance/casedb"/>
            <instance id="commcaresession" src="jr://instance/session"/>
            <session>
              <datum id="case_id"
                nodeset="instance('casedb')/casedb/case[@case_type='parent'][@status='open']"
                value="./@case_id" detail-select="m0_case_short"/>
              <datum id="usercase_id"
                function="instance('casedb')/casedb/case[@case_type='commcare-user'][hq_user_id=instance('commcaresession')/session/context/userid]/@case_id"/>
              <datum id="case_id_child"
                nodeset="instance('casedb')/casedb/case[@case_type='child'][@status='open'][index/parent=instance('commcaresession')/session/data/case_id]"
                value="./@case_id" detail-select="m1_case_short" detail-confirm="m1_case_long"/>
            </session>
            <assertions>
              <assert test="count(instance('casedb')/casedb/case[@case_type='commcare-user'][hq_user_id=instance('commcaresession')/session/context/userid]) = 1">
                <text>
                  <locale id="case_autoload.usercase.case_missing"/>
                </text>
              </assert>
            </assertions>
          </entry>
        </partial>
        """  # noqa: E501
        self.assertXmlPartialEqual(expected, factory.app.create_suite(), "./entry[2]")
