from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.app_manager.const import AUTO_SELECT_USERCASE
from corehq.apps.app_manager.models import (
    AdvancedModule,
    AdvancedOpenCaseAction,
    Application,
    AutoSelectCase,
    CaseIndex,
    LoadUpdateAction,
    Module,
)
from django.test import SimpleTestCase


class ModuleTests(SimpleTestCase):

    def setUp(self):
        self.app = Application.new_app('domain', "Untitled Application")
        self.module = self.app.add_module(Module.new_module('Untitled Module', None))
        self.module.case_type = 'another_case_type'
        self.form = self.module.new_form("Untitled Form", None)


class AdvancedModuleTests(SimpleTestCase):

    def setUp(self):
        self.app = Application.new_app('domain', "Untitled Application")
        self.module = self.app.add_module(AdvancedModule.new_module('Untitled Module', None))
        self.form = self.module.new_form("Untitled Form", None)

    def test_registration_form_simple(self):
        self.form.actions.open_cases = [
            AdvancedOpenCaseAction(
                case_tag="phone",
                case_type="phone",
                name_path="/data/question1",
            )
        ]

        self.assertTrue(self.form.is_registration_form())

    def test_registration_form_subcase(self):
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type="parent",
            case_tag="parent"
        ))
        self.form.actions.open_cases = [
            AdvancedOpenCaseAction(
                case_tag="child",
                case_type="child",
                name_path="/data/question1",
                case_indices=[CaseIndex(tag="parent")]
            )
        ]

        self.assertTrue(self.form.is_registration_form())

    def test_registration_form_autoload(self):
        self.form.actions.load_update_cases = [
            LoadUpdateAction(
                auto_select=AutoSelectCase(mode=AUTO_SELECT_USERCASE, value_key=""),
            )
        ]

        self.form.actions.open_cases = [
            AdvancedOpenCaseAction(
                case_tag="child",
                case_type="child",
                name_path="/data/question1",
            )
        ]

        self.assertTrue(self.form.is_registration_form())

    def test_registration_form_autoload_subcase(self):
        self.form.actions.load_update_cases = [
            LoadUpdateAction(
                case_type="parent",
                case_tag="parent"
            ),
            LoadUpdateAction(
                auto_select=AutoSelectCase(mode=AUTO_SELECT_USERCASE, value_key=""),
            )
        ]

        self.form.actions.open_cases = [
            AdvancedOpenCaseAction(
                case_tag="child",
                case_type="child",
                name_path="/data/question1",
                case_indices=[CaseIndex(tag="parent")]
            )
        ]

        self.assertTrue(self.form.is_registration_form())

    def test_registration_form_subcase_multiple(self):
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type="parent",
            case_tag="parent"
        ))
        self.form.actions.open_cases = [
            AdvancedOpenCaseAction(
                case_tag="child",
                case_type="child",
                name_path="/data/question1",
                case_indices=[CaseIndex(tag="parent")]
            ),
            AdvancedOpenCaseAction(
                case_tag="grandchild",
                case_type="grandchild",
                name_path="/data/children/question1",
                case_indices=[CaseIndex(tag="child")]
            )
        ]

        self.assertFalse(self.form.is_registration_form())

    def test_registration_form_subcase_multiple_repeat(self):
        self.test_registration_form_subcase_multiple()
        self.form.actions.open_cases[-1].repeat_context = "/data/children"

        self.assertTrue(self.form.is_registration_form())
