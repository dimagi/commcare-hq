# coding=utf-8
from corehq.apps.app_manager.const import CAREPLAN_GOAL, CAREPLAN_TASK
from corehq.apps.app_manager.exceptions import XFormException, XFormValidationError
from corehq.apps.app_manager.models import (
    AdvancedForm,
    AdvancedModule,
    AdvancedOpenCaseAction,
    Application,
    FormAction,
    FormActionCondition,
    LoadUpdateAction,
    Module,
    OpenCaseAction,
    PreloadAction,
    UpdateCaseAction,
    OpenSubCaseAction,
    CaseIndex)
from django.test import SimpleTestCase
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.app_manager.util import new_careplan_module
from corehq.apps.app_manager.xform import XForm
from mock import patch


class FormPreparationV2Test(SimpleTestCase, TestXmlMixin):
    file_path = 'data', 'form_preparation_v2'

    def setUp(self):
        self.app = Application.new_app('domain', 'New App')
        self.app.version = 3
        self.module = self.app.add_module(Module.new_module('New Module', lang='en'))
        self.form = self.app.new_form(0, 'New Form', lang='en')
        self.module.case_type = 'test_case_type'
        self.form.source = self.get_xml('original_form', override_path=('data',))

    def test_no_actions(self):
        self.assertXmlEqual(self.get_xml('no_actions'), self.form.render_xform())

    def test_open_case(self):
        self.form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
        self.form.actions.open_case.condition.type = 'always'
        self.assertXmlEqual(self.get_xml('open_case'), self.form.render_xform())

    def test_open_case_external_id(self):
        self.form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id='/data/question1')
        self.form.actions.open_case.condition.type = 'always'
        self.assertXmlEqual(self.get_xml('open_case_external_id'), self.form.render_xform())

    def test_update_case(self):
        self.form.requires = 'case'
        self.form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        self.form.actions.update_case.condition.type = 'always'
        self.assertXmlEqual(self.get_xml('update_case'), self.form.render_xform())

    def test_update_parent_case(self):
        self.form.requires = 'case'
        self.form.actions.update_case = UpdateCaseAction(update={
            'question1': '/data/question1',
            'parent/question1': '/data/question1',
        })
        self.form.actions.update_case.condition.type = 'always'
        self.assertXmlEqual(self.get_xml('update_parent_case'), self.form.render_xform())

    def test_open_update_case(self):
        self.form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
        self.form.actions.open_case.condition.type = 'always'
        self.form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        self.form.actions.update_case.condition.type = 'always'
        self.assertXmlEqual(self.get_xml('open_update_case'), self.form.render_xform())

    def test_update_preload_case(self):
        self.form.requires = 'case'
        self.form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        self.form.actions.update_case.condition.type = 'always'
        self.form.actions.case_preload = PreloadAction(preload={'/data/question1': 'question1'})
        self.form.actions.case_preload.condition.type = 'always'
        self.assertXmlEqual(self.get_xml('update_preload_case'), self.form.render_xform())

    def test_update_attachment(self):
        self.form.requires = 'case'
        self.form.source = self.get_xml('attachment')
        self.form.actions.update_case = UpdateCaseAction(update={'photo': '/data/thepicture'})
        self.form.actions.update_case.condition.type = 'always'
        self.assertXmlEqual(self.get_xml('update_attachment_case'), self.form.render_xform())

    def test_close_case(self):
        self.form.requires = 'case'
        self.form.actions.close_case = FormAction()
        self.form.actions.close_case.condition.type = 'always'
        self.assertXmlEqual(self.get_xml('close_case'), self.form.render_xform())

    def test_strip_ignore_retain(self):
        before = self.get_xml('ignore_retain')
        after = self.get_xml('ignore_retain_stripped')
        xform = XForm(before)
        xform.strip_vellum_ns_attributes()
        self.assertXmlEqual(xform.render(), after)

    def test_empty_itext(self):
        self.app.langs = ['fra']  # lang that's not in the form
        with self.assertRaises(XFormException):
            self.form.render_xform()

    def test_instance_check(self):
        xml = self.get_xml('missing_instances')
        with self.assertRaises(XFormValidationError) as cm:
            XForm(xml).add_missing_instances()
        exception_message = str(cm.exception)
        self.assertIn('casebd', exception_message)
        self.assertIn('custom2', exception_message)


class SubcaseRepeatTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'form_preparation_v2')

    def test_subcase_repeat(self):
        self.app = Application.wrap(self.get_json('subcase-repeat'))
        self.app.case_sharing = False
        self.assertXmlEqual(self.app.get_module(0).get_form(0).render_xform(),
                            self.get_xml('subcase-repeat'))

    def test_subcase_repeat_sharing(self):
        self.app = Application.wrap(self.get_json('subcase-repeat'))
        self.app.case_sharing = True
        self.assertXmlEqual(self.app.get_module(0).get_form(0).render_xform(),
                            self.get_xml('subcase-repeat-sharing'))

    def test_subcase_multiple_repeats(self):
        self.app = Application.wrap(self.get_json('multiple_subcase_repeat'))
        self.assertXmlEqual(self.app.get_module(0).get_form(0).render_xform(),
                            self.get_xml('multiple_subcase_repeat'))

    def test_subcase_repeat_mixed_form(self):
        app = Application.new_app(None, "Untitled Application")
        module_0 = app.add_module(Module.new_module('parent', None))
        module_0.unique_id = 'm0'
        module_0.case_type = 'parent'
        form = app.new_form(0, "Form", None, attachment=self.get_xml('subcase_repeat_mixed_form_pre'))

        module_1 = app.add_module(Module.new_module('subcase', None))
        module_1.unique_id = 'm1'
        module_1.case_type = 'subcase'

        form.actions.open_case = OpenCaseAction(name_path="/data/parent_name")
        form.actions.open_case.condition.type = 'always'

        form.actions.subcases.append(OpenSubCaseAction(
            case_type=module_1.case_type,
            case_name="/data/first_child_name",
            condition=FormActionCondition(type='always')
        ))
        # subcase in the middle that has a repeat context
        form.actions.subcases.append(OpenSubCaseAction(
            case_type=module_1.case_type,
            case_name="/data/repeat_child/repeat_child_name",
            repeat_context='/data/repeat_child',
            condition=FormActionCondition(type='always')
        ))
        form.actions.subcases.append(OpenSubCaseAction(
            case_type=module_1.case_type,
            case_name="/data/last_child_name",
            condition=FormActionCondition(type='always')
        ))

        self.assertXmlEqual(self.get_xml('subcase_repeat_mixed_form_post'),
                            app.get_module(0).get_form(0).render_xform())


class SubcaseParentRefTeset(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'form_preparation_v2')

    def setUp(self):
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()

    def test_parent_ref(self):
        self.app = Application.wrap(self.get_json('subcase-parent-ref'))
        self.assertXmlEqual(self.app.get_module(1).get_form(0).render_xform(),
                            self.get_xml('subcase-parent-ref'))


class CaseSharingFormPrepTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'form_preparation_v2')

    def test_subcase_repeat(self):
        self.app = Application.wrap(self.get_json('complex-case-sharing'))
        self.assertXmlEqual(self.app.get_module(0).get_form(0).render_xform(),
                            self.get_xml('complex-case-sharing'))


class GPSFormPrepTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'form_preparation_v2')

    def setUp(self):
        self.app = Application.wrap(self.get_json('gps'))

    def test_form_with_gps_question(self):
        self.assertXmlEqual(self.app.get_module(0).get_form(0).render_xform(),
                            self.get_xml('gps_with_question'))

    def test_form_without_gps_question(self):
        self.assertXmlEqual(self.app.get_module(0).get_form(1).render_xform(),
                            self.get_xml('gps_no_question'))

    def test_form_with_gps_question_auto(self):
        self.app.auto_gps_capture = True
        self.assertXmlEqual(self.app.get_module(0).get_form(0).render_xform(),
                            self.get_xml('gps_with_question_auto'))

    def test_form_without_gps_question_auto(self):
        self.app.auto_gps_capture = True
        self.assertXmlEqual(self.app.get_module(0).get_form(1).render_xform(),
                            self.get_xml('gps_no_question_auto'))


class FormPreparationCareplanTest(SimpleTestCase, TestXmlMixin):
    file_path = 'data', 'form_preparation_careplan'

    def setUp(self):
        self.app = Application.new_app('domain', 'New App')
        self.app.version = 3
        self.module = self.app.add_module(Module.new_module('New Module', lang='en'))
        self.form = self.app.new_form(0, 'New Form', lang='en')
        self.module.case_type = 'test_case_type'
        self.form.source = self.get_xml('original_form', override_path=('data',))
        self.form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
        self.form.actions.open_case.condition.type = 'always'

        self.careplan_module = new_careplan_module(self.app, None, None, self.module)

    def test_create_goal(self):
        form = self.careplan_module.get_form_by_type(CAREPLAN_GOAL, 'create')
        self.assertXmlEqual(form.render_xform(), self.get_xml('create_goal'))

    def test_update_goal(self):
        form = self.careplan_module.get_form_by_type(CAREPLAN_GOAL, 'update')
        self.assertXmlEqual(form.render_xform(), self.get_xml('update_goal'))

    def test_create_task(self):
        form = self.careplan_module.get_form_by_type(CAREPLAN_TASK, 'create')
        self.assertXmlEqual(form.render_xform(), self.get_xml('create_task'))

    def test_update_task(self):
        form = self.careplan_module.get_form_by_type(CAREPLAN_TASK, 'update')
        self.assertXmlEqual(form.render_xform(), self.get_xml('update_task'))


class FormPreparationV2TestAdvanced(SimpleTestCase, TestXmlMixin):
    file_path = 'data', 'form_preparation_v2_advanced'

    def setUp(self):
        self.app = Application.new_app('domain', 'New App')
        self.app.version = 3
        self.module = self.app.add_module(AdvancedModule.new_module('New Module', lang='en'))
        self.module.case_type = 'test_case_type'
        self.form = self.module.new_form("Untitled Form", "en", self.get_xml('original_form', override_path=('data',)))

        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()

    def test_no_actions(self):
        self.assertXmlEqual(self.get_xml('no_actions'), self.form.render_xform())

    def test_open_case(self):
        self.form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type=self.module.case_type,
            case_tag='open_1',
            name_path="/data/question1"
        ))
        self.form.actions.open_cases[0].open_condition.type = 'always'
        self.assertXmlEqual(self.get_xml('open_case'), self.form.render_xform())

    def test_update_case(self):
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.module.case_type,
            case_tag='load_1',
            case_properties={'question1': '/data/question1'}
        ))
        self.assertXmlEqual(self.get_xml('update_case'), self.form.render_xform())

    def test_open_update_case(self):
        self.form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type=self.module.case_type,
            case_tag='open_1',
            name_path="/data/question1",
            case_properties={'question1': '/data/question1'}
        ))
        self.form.actions.open_cases[0].open_condition.type = 'always'
        self.assertXmlEqual(self.get_xml('open_update_case'), self.form.render_xform())

    def test_open_close_case(self):
        self.form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type=self.module.case_type,
            case_tag='open_1',
            name_path="/data/question1",
        ))
        self.form.actions.open_cases[0].open_condition.type = 'always'
        self.form.actions.open_cases[0].close_condition.type = 'always'
        self.assertXmlEqual(self.get_xml('open_close_case'), self.form.render_xform())

    def test_update_preload_case(self):
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.module.case_type,
            case_tag='load_1',
            case_properties={'question1': '/data/question1'},
            preload={'/data/question1': 'question1'}
        ))
        self.assertXmlEqual(self.get_xml('update_preload_case'), self.form.render_xform())

    def test_close_case(self):
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.module.case_type,
            case_tag='load_1',
        ))
        self.form.actions.load_update_cases[0].close_condition.type = 'always'
        self.assertXmlEqual(self.get_xml('close_case'), self.form.render_xform())

    def test_update_preload_multiple_case(self):
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.module.case_type,
            case_tag='load_1',
            case_properties={'question1': '/data/question1'},
            preload={'/data/question1': 'question1'}
        ))
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.module.case_type,
            case_tag='load_2',
            case_properties={'question2': '/data/question2'},
            preload={'/data/question2': 'question2'}
        ))
        self.assertXmlEqual(self.get_xml('update_preload_case_multiple'), self.form.render_xform())

    def test_update_parent_case(self):
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.module.case_type,
            case_tag='load_1',
            case_properties={'question1': '/data/question1', 'parent/question1': '/data/question1'}
        ))
        self.assertXmlEqual(self.get_xml('update_parent_case'), self.form.render_xform())

    def test_update_attachment(self):
        self.form.source = self.get_xml('attachment')
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.module.case_type,
            case_tag='load_1',
            case_properties={'photo': '/data/thepicture'}
        ))
        self.assertXmlEqual(self.get_xml('update_attachment_case'), self.form.render_xform())


class FormPreparationChildModules(SimpleTestCase, TestXmlMixin):
    file_path = 'data', 'form_preparation_v2_advanced'

    def setUp(self):
        self.app = Application.new_app('domain', 'New App')
        self.app.version = 3

    def test_child_module_adjusted_datums_advanced_module(self):
        """
        Testing that the session variable name for the case_id is correct since
        it will have been adjusted in the suite.xml to match the variable name
        in the root module.
        """
        module = self.app.add_module(AdvancedModule.new_module('New Module', lang='en'))
        module.case_type = 'test_case_type'
        form = module.new_form("Untitled Form", "en", self.get_xml('original_form', override_path=('data',)))

        form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=module.case_type,
            case_tag='load_1',
            case_properties={'question1': '/data/question1'}
        ))

        root_module = self.app.add_module(Module.new_module('root module', None))
        root_module.unique_id = 'm_root'
        root_module.case_type = module.case_type

        root_module_form = root_module.new_form('root module form', None)
        root_module_form.requires = 'case'
        root_module_form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        root_module_form.actions.update_case.condition.type = 'always'

        # make module a child module of root_module
        module.root_module_id = root_module.unique_id

        self.assertXmlEqual(self.get_xml('child_module_adjusted_case_id_advanced'), form.render_xform())

    def test_child_module_adjusted_datums_basic_module(self):
        """
        Testing that the session variable name for the case_id is correct since
        it will have been adjusted in the suite.xml to match the variable name
        in the root module.
        """
        module = self.app.add_module(Module.new_module('New Module', lang='en'))
        module.case_type = 'guppy'
        form = module.new_form("Untitled Form", "en", self.get_xml('original_form', override_path=('data',)))

        form.requires = 'case'
        form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        form.actions.update_case.condition.type = 'always'

        root_module = self.app.add_module(Module.new_module('root module', None))
        root_module.unique_id = 'm_root'
        root_module.case_type = 'test_case_type'

        root_module_form = root_module.new_form('root module form', None)
        root_module_form.requires = 'case'
        root_module_form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        root_module_form.actions.update_case.condition.type = 'always'

        # make module a child module of root_module
        module.root_module_id = root_module.unique_id

        module.parent_select.active = True
        module.parent_select.module_id = root_module.unique_id

        self.assertXmlEqual(self.get_xml('child_module_adjusted_case_id_basic'), form.render_xform())


class BaseIndexTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'form_preparation_v2_advanced')

    def setUp(self):
        self.app = Application.new_app('domain', 'New App')
        self.app.version = 3
        self.parent_module = self.app.add_module(Module.new_module('New Module', lang='en'))
        self.parent_form = self.app.new_form(0, 'New Form', lang='en')
        self.parent_module.case_type = 'parent_test_case_type'
        self.parent_form.source = self.get_xml('original_form', override_path=('data',))
        self.parent_form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
        self.parent_form.actions.open_case.condition.type = 'always'

        self.module = self.app.add_module(AdvancedModule.new_module('New Module', lang='en'))
        form = AdvancedForm(name={"en": "Untitled Form"})
        self.module.forms.append(form)
        self.form = self.module.get_form(-1)
        self.module.case_type = 'test_case_type'
        self.form.source = self.get_xml('subcase_original')

        child_module_1 = self.app.add_module(Module.new_module('New Module', lang='en'))
        child_module_1.case_type ='child1'
        child_module_2 = self.app.add_module(Module.new_module('New Module', lang='en'))
        child_module_2.case_type ='child2'
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()


class SubcaseRepeatTestAdvanced(BaseIndexTest):

    def test_subcase(self):
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.parent_module.case_type,
            case_tag='load_1',
        ))
        self.form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type=self.module.case_type,
            case_tag='open_1',
            name_path='/data/mother_name',
            case_indices=[CaseIndex(tag='load_1')]
        ))
        self.form.actions.open_cases[0].open_condition.type = 'always'
        self.assertXmlEqual(self.get_xml('subcase'), self.form.render_xform())

    def test_subcase_repeat(self):
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.parent_module.case_type,
            case_tag='load_1',
        ))
        self.form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type=self.module.case_type,
            case_tag='open_1',
            name_path='/data/mother_name',
            case_indices=[CaseIndex(tag='load_1')],
            repeat_context="/data/child"
        ))
        self.form.actions.open_cases[0].open_condition.type = 'always'
        self.assertXmlEqual(self.get_xml('subcase-repeat'), self.form.render_xform())

    def test_subcase_of_open(self):
        self.form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type=self.parent_module.case_type,
            case_tag='open_1',
            name_path='/data/mother_name',
        ))

        self.form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type=self.module.case_type,
            case_tag='open_2',
            name_path='/data/mother_name',
            case_indices=[CaseIndex(tag='open_1')],
            repeat_context="/data/child"
        ))
        for action in self.form.actions.open_cases:
            action.open_condition.type = 'always'
        self.assertXmlEqual(self.get_xml('subcase-open'), self.form.render_xform())

    def test_subcase_repeat_sharing(self):
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.parent_module.case_type,
            case_tag='load_1',
        ))
        self.form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type=self.module.case_type,
            case_tag='open_1',
            name_path='/data/mother_name',
            case_indices=[CaseIndex(tag='load_1')],
            repeat_context="/data/child"
        ))
        self.form.actions.open_cases[0].open_condition.type = 'always'
        self.app.case_sharing = True
        self.assertXmlEqual(self.get_xml('subcase-repeat-sharing'), self.form.render_xform())

    def test_subcase_multiple_repeats(self):
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.parent_module.case_type,
            case_tag='load_1',
        ))
        self.form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type='child1',
            case_tag='open_1',
            name_path='/data/mother_name',
            case_indices=[CaseIndex(tag='load_1')],
            repeat_context="/data/child",
        ))
        self.form.actions.open_cases[0].open_condition.type = 'if'
        self.form.actions.open_cases[0].open_condition.question = '/data/child/which_child'
        self.form.actions.open_cases[0].open_condition.answer = '1'

        self.form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type='child2',
            case_tag='open_2',
            name_path='/data/mother_name',
            case_indices=[CaseIndex(tag='load_1')],
            repeat_context="/data/child",
        ))
        self.form.actions.open_cases[1].open_condition.type = 'if'
        self.form.actions.open_cases[1].open_condition.question = '/data/child/which_child'
        self.form.actions.open_cases[1].open_condition.answer = '2'
        self.assertXmlEqual(self.get_xml('subcase-repeat-multiple'), self.form.render_xform())


class TestExtensionCase(BaseIndexTest):

    def test_relationship_added_to_form(self):
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.parent_module.case_type,
            case_tag='load_1',
        ))
        self.form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type='child1',
            case_tag='open_1',
            name_path='/data/mother_name',
            case_indices=[CaseIndex(tag='load_1'),
                          CaseIndex(tag='load_1', reference_id='host', relationship='extension')],
            repeat_context="/data/child",
        ))

        self.assertXmlEqual(self.get_xml('extension-case'), self.form.render_xform())


class TestXForm(SimpleTestCase, TestXmlMixin):
    file_path = "data", "xform_test"

    def test_action_relevance(self):
        xform = XForm('')

        def condition_case(expected, type=None, question=None, answer=None, operator=None):
            condition = FormActionCondition(
                type=type,
                question=question,
                answer=answer,
                operator=operator
            )
            return condition, expected

        cases = [
            (condition_case('true()', 'always')),
            (condition_case('false()', 'never')),
            (condition_case("/data/question1 = 'yes'", 'if', '/data/question1', 'yes')),
            (condition_case("selected(/data/question1, 'yes')", 'if', '/data/question1', 'yes', 'selected')),
            (condition_case("/data/question1", 'if', '/data/question1', None, 'boolean_true')),
        ]

        for case in cases:
            actual = xform.action_relevance(case[0])
            self.assertEqual(actual, case[1])

    @classmethod
    def construct_form(cls):
        app = Application.new_app('domain', 'New App')
        app.add_module(Module.new_module('New Module', lang='en'))
        form = app.new_form(0, 'MySuperSpecialForm', lang='en')
        return form

    def test_set_name(self):

        form = self.construct_form()
        form.source = self.get_file("MySuperSpecialForm", "xml")

        xform = form.wrapped_xform()
        rendered_form = xform.render()

        xform.set_name("NewTotallyAwesomeName")
        new_rendered_form = xform.render()

        self.assertEqual(
            rendered_form.replace(
                "MySuperSpecialForm",
                "NewTotallyAwesomeName"
            ),
            new_rendered_form
        )

    def test_set_name_on_empty_form(self):
        form = self.construct_form()
        form.wrapped_xform().set_name("Passes if there is no exception")
