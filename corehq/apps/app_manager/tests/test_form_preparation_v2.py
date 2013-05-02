# coding=utf-8
from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, OpenCaseAction, UpdateCaseAction, PreloadAction, FormAction, Detail
from django.test import TestCase
from corehq.apps.app_manager.tests.util import TestFileMixin

class FormPreparationV2Test(TestCase, TestFileMixin):
    file_path = 'data', 'form_preparation_v2'
    def setUp(self):
        self.app = Application.new_app('domain', 'New App', APP_V2)
        self.app.version = 3
        self.module = self.app.new_module('New Module', lang='en')
        self.form = self.app.new_form(0, 'New Form', lang='en')
        self.module.case_type = 'test_case_type'
        self.form.source = self.get_xml('original')

    def test_no_actions(self):
        check_xml_line_by_line(self, self.get_xml('no_actions'), self.form.render_xform())

    def test_open_case(self):
        self.form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
        self.form.actions.open_case.condition.type = 'always'
        check_xml_line_by_line(self, self.get_xml('open_case'), self.form.render_xform())

    def test_open_case_external_id(self):
        self.form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id='/data/question1')
        self.form.actions.open_case.condition.type = 'always'
        check_xml_line_by_line(self, self.get_xml('open_case_external_id'), self.form.render_xform())

    def test_update_case(self):
        self.form.requires = 'case'
        self.form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        self.form.actions.update_case.condition.type = 'always'
        check_xml_line_by_line(self, self.get_xml('update_case'), self.form.render_xform())

    def test_open_update_case(self):
        self.form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
        self.form.actions.open_case.condition.type = 'always'
        self.form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        self.form.actions.update_case.condition.type = 'always'
        check_xml_line_by_line(self, self.get_xml('open_update_case'), self.form.render_xform())

    def test_update_preload_case(self):
        self.form.requires = 'case'
        self.form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        self.form.actions.update_case.condition.type = 'always'
        self.form.actions.case_preload = PreloadAction(preload={'/data/question1': 'question1'})
        self.form.actions.case_preload.condition.type = 'always'
        check_xml_line_by_line(self, self.get_xml('update_preload_case'), self.form.render_xform())

    def test_close_case(self):
        self.form.requires = 'case'
        self.form.actions.close_case = FormAction()
        self.form.actions.close_case.condition.type = 'always'
        check_xml_line_by_line(self, self.get_xml('close_case'), self.form.render_xform())
