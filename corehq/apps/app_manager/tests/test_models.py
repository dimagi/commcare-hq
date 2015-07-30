from corehq.apps.app_manager.const import APP_V2, USERCASE_TYPE
from corehq.apps.app_manager.models import Application, Module, UpdateCaseAction, AdvancedModule, LoadUpdateAction
from django.test import SimpleTestCase
from mock import patch


class ModuleTests(SimpleTestCase):

    def setUp(self):
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()
        self.is_usercase_in_use_mock.return_value = True

        self.app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)
        self.module = self.app.add_module(Module.new_module('Untitled Module', None))
        self.module.case_type = 'another_case_type'
        self.form = self.module.new_form("Untitled Form", None)

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()

    def test_is_usercaseonly_no_usercase(self):
        """
        is_usercaseonly should return False if the usercase is not updated
        """
        self.assertFalse(self.module.is_usercaseonly())

    def test_is_usercaseonly_other_case(self):
        """
        is_usercaseonly should return False if another case type is updated
        """
        self.form.requires = 'case'
        self.form.actions.update_case = UpdateCaseAction(update={'name': '/data/question1'})
        self.form.actions.update_case.condition.type = 'always'
        self.form.actions.usercase_update = UpdateCaseAction(update={'name': '/data/question1'})
        self.form.actions.usercase_update.condition.type = 'always'
        self.assertFalse(self.module.is_usercaseonly())

    def test_is_usercaseonly_usercaseonly(self):
        """
        is_usercaseonly should return True if only the usercase is updated
        """
        self.form.actions.usercase_update = UpdateCaseAction(update={'name': '/data/question1'})
        self.form.actions.usercase_update.condition.type = 'always'
        self.assertTrue(self.module.is_usercaseonly())


class AdvancedModuleTests(SimpleTestCase):

    def setUp(self):
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()
        self.is_usercase_in_use_mock.return_value = True

        self.app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)
        self.module = self.app.add_module(AdvancedModule.new_module('Untitled Module', None))
        self.form = self.module.new_form("Untitled Form", None)
        self.case_type = 'another_case_type'

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()

    def test_is_usercaseonly_no_usercase(self):
        """
        is_usercaseonly should return False if the usercase is not updated
        """
        self.assertFalse(self.module.is_usercaseonly())

    def test_is_usercaseonly_other_case(self):
        """
        is_usercaseonly should return False if another case type is updated
        """
        action = LoadUpdateAction(case_tag=self.case_type, case_type=self.case_type)
        self.form.actions.load_update_cases.append(action)
        action = LoadUpdateAction(case_tag=USERCASE_TYPE, case_type=USERCASE_TYPE)
        self.form.actions.load_update_cases.append(action)
        self.assertFalse(self.module.is_usercaseonly())

    def test_is_usercaseonly_usercaseonly(self):
        """
        is_usercaseonly should return True if only the usercase is updated
        """
        action = LoadUpdateAction(case_tag=USERCASE_TYPE, case_type=USERCASE_TYPE)
        self.form.actions.load_update_cases.append(action)
        self.assertTrue(self.module.is_usercaseonly())
