from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, OpenCaseAction, UpdateCaseAction, PreloadAction, FormAction
from django.test import TestCase
import os

def get_xml(name):
    _ = os.path.dirname(__file__)
    _ = os.path.join(_, 'data')
    _ = os.path.join(_, 'form_preparation_v2')
    _ = os.path.join(_, '%s.xml' % name)
    with open(_) as f:
        return f.read()

XFORM_SOURCE = get_xml('original')
NO_ACTIONS_SOURCE = get_xml('no_actions')
OPEN_CASE_SOURCE = get_xml('open_case')
OPEN_CASE_EXTERNAL_ID_SOURCE = get_xml('open_case_external_id')
UPDATE_CASE_SOURCE = get_xml('update_case')
TASK_MODE_UPDATE_PRELOAD_CASE_SOURCE = get_xml('task_mode_update_preload_case')
OPEN_UPDATE_CASE_SOURCE = get_xml('open_update_case')
UPDATE_PRELOAD_CASE_SOURCE = get_xml('update_preload_case')
CLOSE_CASE_SOURCE = get_xml('close_case')

class FormPreparationV2Test(TestCase):
    def setUp(self):
        self.app = Application.new_app('domain', 'New App', APP_V2)
        self.app.version = 3
        self.module = self.app.new_module('New Module', lang='en')
        self.form = self.app.new_form(0, 'New Form', lang='en')
        self.module.case_type = 'test_case_type'
        self.form.source = XFORM_SOURCE

    def test_no_actions(self):
        check_xml_line_by_line(self, NO_ACTIONS_SOURCE, self.form.render_xform())

    def test_open_case(self):
        self.form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
        self.form.actions.open_case.condition.type = 'always'
        check_xml_line_by_line(self, OPEN_CASE_SOURCE, self.form.render_xform())

    def test_open_case_external_id(self):
        self.form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id='/data/question1')
        self.form.actions.open_case.condition.type = 'always'
        check_xml_line_by_line(self, OPEN_CASE_EXTERNAL_ID_SOURCE, self.form.render_xform())

    def test_update_case(self):
        self.form.requires = 'case'
        self.form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        self.form.actions.update_case.condition.type = 'always'
        check_xml_line_by_line(self, UPDATE_CASE_SOURCE, self.form.render_xform())

    def test_open_update_case(self):
        self.form.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
        self.form.actions.open_case.condition.type = 'always'
        self.form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        self.form.actions.update_case.condition.type = 'always'
        check_xml_line_by_line(self, OPEN_UPDATE_CASE_SOURCE, self.form.render_xform())

    def test_update_preload_case(self):
        self.form.source = XFORM_SOURCE
        self.form.requires = 'case'
        self.form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
        self.form.actions.update_case.condition.type = 'always'
        self.form.actions.case_preload = PreloadAction(preload={'/data/question1': 'question1'})
        self.form.actions.case_preload.condition.type = 'always'
        check_xml_line_by_line(self, UPDATE_PRELOAD_CASE_SOURCE, self.form.render_xform())

    def test_close_case(self):
        self.form.requires = 'case'
        self.form.actions.close_case = FormAction()
        self.form.actions.close_case.condition.type = 'always'
        check_xml_line_by_line(self, CLOSE_CASE_SOURCE, self.form.render_xform())

