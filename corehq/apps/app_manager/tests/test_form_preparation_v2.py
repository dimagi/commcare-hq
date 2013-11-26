# coding=utf-8
import difflib

import io

import lxml.etree

from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.apps.app_manager.const import APP_V2, CAREPLAN_GOAL, CAREPLAN_TASK
from corehq.apps.app_manager.models import Application, OpenCaseAction, UpdateCaseAction, PreloadAction, FormAction, Module, CareplanModule
from django.test import TestCase
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.apps.app_manager.util import new_careplan_module


class FormPrepBase(TestCase, TestFileMixin):
    def assert_xml_equiv(self, actual, expected):
        actual_canonicalized = io.BytesIO()
        expected_canonicalized = io.BytesIO()

        parser = lxml.etree.XMLParser(remove_blank_text=True)

        lxml.etree.fromstring(actual, parser=parser).getroottree().write_c14n(actual_canonicalized)
        lxml.etree.fromstring(expected, parser=parser).getroottree().write_c14n(expected_canonicalized)

        if actual_canonicalized.getvalue() != expected_canonicalized.getvalue():
            check_xml_line_by_line(self, actual, expected)


class FormPreparationV2Test(FormPrepBase):
    file_path = 'data', 'form_preparation_v2'
    def setUp(self):
        self.app = Application.new_app('domain', 'New App', APP_V2)
        self.app.version = 3
        self.module = self.app.add_module(Module.new_module('New Module', lang='en'))
        self.form = self.app.new_form(0, 'New Form', lang='en')
        self.module.case_type = 'test_case_type'
        self.form.source = self.get_xml('original')

    def test_no_actions(self):
        self.assert_xml_equiv(self.get_xml('no_actions'), self.form.render_xform())

    def test_open_case(self):
        self.form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
        self.form.actions.open_case.condition.type = 'always'
        self.assert_xml_equiv(self.get_xml('open_case'), self.form.render_xform())

    def test_open_case_external_id(self):
        self.form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id='/data/question1')
        self.form.actions.open_case.condition.type = 'always'
        self.assert_xml_equiv(self.get_xml('open_case_external_id'), self.form.render_xform())

    def test_update_case(self):
        self.form.requires = 'case'
        self.form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        self.form.actions.update_case.condition.type = 'always'
        self.assert_xml_equiv(self.get_xml('update_case'), self.form.render_xform())

    def test_open_update_case(self):
        self.form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
        self.form.actions.open_case.condition.type = 'always'
        self.form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        self.form.actions.update_case.condition.type = 'always'
        self.assert_xml_equiv(self.get_xml('open_update_case'), self.form.render_xform())

    def test_update_preload_case(self):
        self.form.requires = 'case'
        self.form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        self.form.actions.update_case.condition.type = 'always'
        self.form.actions.case_preload = PreloadAction(preload={'/data/question1': 'question1'})
        self.form.actions.case_preload.condition.type = 'always'
        self.assert_xml_equiv(self.get_xml('update_preload_case'), self.form.render_xform())

    def test_close_case(self):
        self.form.requires = 'case'
        self.form.actions.close_case = FormAction()
        self.form.actions.close_case.condition.type = 'always'
        self.assert_xml_equiv(self.get_xml('close_case'), self.form.render_xform())


class SubcaseRepeatTest(FormPrepBase):
    file_path = ('data', 'form_preparation_v2')

    def test_subcase_repeat(self):
        self.app = Application.wrap(self.get_json('subcase-repeat'))
        self.app.case_sharing = False
        self.assert_xml_equiv(self.app.get_module(0).get_form(0).render_xform(),
                              self.get_xml('subcase-repeat'))

    def test_subcase_repeat_sharing(self):
        self.app = Application.wrap(self.get_json('subcase-repeat'))
        self.app.case_sharing = True
        self.assert_xml_equiv(self.app.get_module(0).get_form(0).render_xform(),
                              self.get_xml('subcase-repeat-sharing'))

    def test_subcase_multiple_repeats(self):
        self.app = Application.wrap(self.get_json('multiple_subcase_repeat'))
        self.assert_xml_equiv(self.app.get_module(0).get_form(0).render_xform(),
                              self.get_xml('multiple_subcase_repeat'))


class SubcaseParentRefTeset(FormPrepBase):
    file_path = ('data', 'form_preparation_v2')

    def test_parent_ref(self):
        self.app = Application.wrap(self.get_json('subcase-parent-ref'))
        self.assert_xml_equiv(self.app.get_module(1).get_form(0).render_xform(),
                              self.get_xml('subcase-parent-ref'))


class CaseSharingFormPrepTest(FormPrepBase):
    file_path = ('data', 'form_preparation_v2')

    def test_subcase_repeat(self):
        self.app = Application.wrap(self.get_json('complex-case-sharing'))
        self.assert_xml_equiv(self.app.get_module(0).get_form(0).render_xform(),
                              self.get_xml('complex-case-sharing'))

class FormPreparationCareplanTest(FormPrepBase):
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
        self.assert_xml_equiv(form.render_xform(), self.get_xml('create_goal'))

    def test_update_goal(self):
        form = self.careplan_module.get_form_by_type(CAREPLAN_GOAL, 'update')
        self.assert_xml_equiv(form.render_xform(), self.get_xml('update_goal'))

    def test_create_task(self):
        form = self.careplan_module.get_form_by_type(CAREPLAN_TASK, 'create')
        self.assert_xml_equiv(form.render_xform(), self.get_xml('create_task'))

    def test_update_task(self):
        form = self.careplan_module.get_form_by_type(CAREPLAN_TASK, 'update')
        self.assert_xml_equiv(form.render_xform(), self.get_xml('update_task'))
