# coding=utf-8
import lxml
from corehq.apps.app_manager.const import APP_V2, CAREPLAN_GOAL, CAREPLAN_TASK
from corehq.apps.app_manager.models import Application, OpenCaseAction, UpdateCaseAction, PreloadAction, FormAction, Module, AdvancedModule, AdvancedForm, AdvancedOpenCaseAction, LoadUpdateAction, \
    AutoSelectCase, FormActionCondition, FormSchedule, ScheduleVisit
from django.test import SimpleTestCase as TestCase
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.apps.app_manager.util import new_careplan_module
from corehq.apps.app_manager.xform import XForm


class FormPreparationV2Test(TestCase, TestFileMixin):
    file_path = 'data', 'form_preparation_v2'
    def setUp(self):
        self.app = Application.new_app('domain', 'New App', APP_V2)
        self.app.version = 3
        self.module = self.app.add_module(Module.new_module('New Module', lang='en'))
        self.form = self.app.new_form(0, 'New Form', lang='en')
        self.module.case_type = 'test_case_type'
        self.form.source = self.get_xml('original')

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


class SubcaseRepeatTest(TestCase, TestFileMixin):
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


class SubcaseParentRefTeset(TestCase, TestFileMixin):
    file_path = ('data', 'form_preparation_v2')

    def test_parent_ref(self):
        self.app = Application.wrap(self.get_json('subcase-parent-ref'))
        self.assertXmlEqual(self.app.get_module(1).get_form(0).render_xform(),
                              self.get_xml('subcase-parent-ref'))


class CaseSharingFormPrepTest(TestCase, TestFileMixin):
    file_path = ('data', 'form_preparation_v2')

    def test_subcase_repeat(self):
        self.app = Application.wrap(self.get_json('complex-case-sharing'))
        self.assertXmlEqual(self.app.get_module(0).get_form(0).render_xform(),
                              self.get_xml('complex-case-sharing'))


class GPSFormPrepTest(TestCase, TestFileMixin):
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


class FormPreparationCareplanTest(TestCase, TestFileMixin):
    file_path = 'data', 'form_preparation_careplan'
    def setUp(self):
        self.app = Application.new_app('domain', 'New App', APP_V2)
        self.app.version = 3
        self.module = self.app.add_module(Module.new_module('New Module', lang='en'))
        self.form = self.app.new_form(0, 'New Form', lang='en')
        self.module.case_type = 'test_case_type'
        self.form.source = self.get_xml('original')
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



class FormPreparationV2TestAdvanced(TestCase, TestFileMixin):
    file_path = 'data', 'form_preparation_v2_advanced'
    def setUp(self):
        self.app = Application.new_app('domain', 'New App', APP_V2)
        self.app.version = 3
        self.module = self.app.add_module(AdvancedModule.new_module('New Module', lang='en'))
        form = AdvancedForm(name={"en": "Untitled Form"})
        self.module.forms.append(form)
        self.form = self.module.get_form(-1)
        self.module.case_type = 'test_case_type'
        self.form.source = self.get_xml('original')

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
            preload={'question1': '/data/question1'}
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
            preload={'question1': '/data/question1'}
        ))
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.module.case_type,
            case_tag='load_2',
            case_properties={'question2': '/data/question2'},
            preload={'question2': '/data/question2'}
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

    def test_schedule(self):
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.module.case_type,
            case_tag='load_1',
            case_properties={'question1': '/data/question1'}
        ))
        self.module.has_schedule = True
        self.form.schedule = FormSchedule(anchor='edd')
        xml = self.get_xml('schedule').format(
            form_id=self.form.schedule_form_id,
            form_index=1
        )
        self.assertXmlEqual(xml, self.form.render_xform())

    def test_schedule_index(self):
        self.module.has_schedule = True
        form = self.app.new_form(0, 'New Form', lang='en')
        form.source = self.get_xml('original')
        form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.module.case_type,
            case_tag='load_1',
            case_properties={'question1': '/data/question1'}
        ))
        form.schedule = FormSchedule(anchor='edd')

        xml = self.get_xml('schedule').format(
            form_id=form.schedule_form_id,
            form_index=2
        )
        self.assertXmlEqual(xml, form.render_xform())

class SubcaseRepeatTestAdvanced(TestCase, TestFileMixin):
    file_path = ('data', 'form_preparation_v2_advanced')

    def setUp(self):
        self.app = Application.new_app('domain', 'New App', APP_V2)
        self.app.version = 3
        self.parent_module = self.app.add_module(Module.new_module('New Module', lang='en'))
        self.parent_form = self.app.new_form(0, 'New Form', lang='en')
        self.parent_module.case_type = 'parent_test_case_type'
        self.parent_form.source = self.get_xml('original')
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


    def test_subcase(self):
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.parent_module.case_type,
            case_tag='load_1',
        ))
        self.form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type=self.module.case_type,
            case_tag='open_1',
            name_path='/data/mother_name',
            parent_tag='load_1'
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
            parent_tag='load_1',
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
            parent_tag='open_1',
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
            parent_tag='load_1',
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
            parent_tag='load_1',
            repeat_context="/data/child",
        ))
        self.form.actions.open_cases[0].open_condition.type = 'if'
        self.form.actions.open_cases[0].open_condition.question = '/data/child/which_child'
        self.form.actions.open_cases[0].open_condition.answer = '1'

        self.form.actions.open_cases.append(AdvancedOpenCaseAction(
            case_type='child2',
            case_tag='open_2',
            name_path='/data/mother_name',
            parent_tag='load_1',
            repeat_context="/data/child",
        ))
        self.form.actions.open_cases[1].open_condition.type = 'if'
        self.form.actions.open_cases[1].open_condition.question = '/data/child/which_child'
        self.form.actions.open_cases[1].open_condition.answer = '2'
        self.assertXmlEqual(self.get_xml('subcase-repeat-multiple'), self.form.render_xform())


class TestXForm(TestCase):
    def setUp(self):
        self.xform = XForm('')

    def test_action_relevance(self):
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
        ]

        for case in cases:
            actual = self.xform.action_relevance(case[0])
            self.assertEqual(actual, case[1])
