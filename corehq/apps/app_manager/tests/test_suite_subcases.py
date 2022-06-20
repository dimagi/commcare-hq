from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    Application,
    ConditionalCaseUpdate,
    FormActionCondition,
    Module,
    OpenCaseAction,
    OpenSubCaseAction,
    UpdateCaseAction,
)
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    TestXmlMixin,
    patch_get_xform_resource_overrides,
)


@patch_get_xform_resource_overrides()
class SuiteSubcasesTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def test_open_case_and_subcase(self, *args):
        app = Application.new_app('domain', "Untitled Application")

        module = app.add_module(Module.new_module('parent', None))
        module.case_type = 'phone'
        module.unique_id = 'm0'

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://m0-f0'
        form.actions.open_case = OpenCaseAction(name_update=ConditionalCaseUpdate(question_path="/data/question1"))
        form.actions.open_case.condition.type = 'always'
        form.actions.subcases.append(OpenSubCaseAction(
            case_type='tablet',
            name_update=ConditionalCaseUpdate(question_path="/data/question1"),
            condition=FormActionCondition(type='always')
        ))

        self.assertXmlPartialEqual(self.get_xml('open_case_and_subcase'), app.create_suite(), "./entry[1]")

    def test_update_and_subcase(self, *args):
        app = Application.new_app('domain', "Untitled Application")

        module = app.add_module(Module.new_module('parent', None))
        module.case_type = 'phone'
        module.unique_id = 'm0'

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://m0-f0'
        form.requires = 'case'
        form.actions.update_case = UpdateCaseAction(
            update={'question1': ConditionalCaseUpdate(question_path='/data/question1')})
        form.actions.update_case.condition.type = 'always'
        form.actions.subcases.append(OpenSubCaseAction(
            case_type=module.case_type,
            name_update=ConditionalCaseUpdate(question_path="/data/question1"),
            condition=FormActionCondition(type='always')
        ))

        self.assertXmlPartialEqual(self.get_xml('update_case_and_subcase'), app.create_suite(), "./entry[1]")

    def test_subcase_repeat_mixed(self, *args):
        app = Application.new_app(None, "Untitled Application")
        module_0 = app.add_module(Module.new_module('parent', None))
        module_0.unique_id = 'm0'
        module_0.case_type = 'parent'
        form = app.new_form(0, "Form", None)

        form.actions.open_case = OpenCaseAction(name_update=ConditionalCaseUpdate(question_path="/data/question1"))
        form.actions.open_case.condition.type = 'always'

        child_case_type = 'child'
        form.actions.subcases.append(OpenSubCaseAction(
            case_type=child_case_type,
            name_update=ConditionalCaseUpdate(question_path="/data/question1"),
            condition=FormActionCondition(type='always')
        ))
        # subcase in the middle that has a repeat context
        form.actions.subcases.append(OpenSubCaseAction(
            case_type=child_case_type,
            name_update=ConditionalCaseUpdate(question_path="/data/repeat/question1"),
            repeat_context='/data/repeat',
            condition=FormActionCondition(type='always')
        ))
        form.actions.subcases.append(OpenSubCaseAction(
            case_type=child_case_type,
            name_update=ConditionalCaseUpdate(question_path="/data/question1"),
            condition=FormActionCondition(type='always')
        ))

        expected = """
        <partial>
            <session>
              <datum id="case_id_new_parent_0" function="uuid()"/>
              <datum id="case_id_new_child_1" function="uuid()"/>
              <datum id="case_id_new_child_3" function="uuid()"/>
            </session>
        </partial>
        """
        self.assertXmlPartialEqual(expected,
                                   app.create_suite(),
                                   './entry[1]/session')
