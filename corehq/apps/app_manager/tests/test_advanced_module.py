from django.test import SimpleTestCase
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, AdvancedForm, AdvancedModule, LoadUpdateAction, AutoSelectCase, \
    AUTO_SELECT_USER
from corehq.apps.app_manager.tests.util import TestFileMixin


def add_load_action(form, case_type, tag):
    form.actions.load_update_cases.append(LoadUpdateAction(
        case_type=case_type,
        case_tag=tag,
    ))


class AdvancedModuleFormFilteringTest(SimpleTestCase, TestFileMixin):
    """
    Test rules for allowing form filtering in AdvancedModules

    * module is not configured a 'put_in_root'
    * all forms require a case (at least one load action that isn't and auto-select)
    * the first "load" action of each form must have the same case tag (excluding auto-load actions)
    """

    def setUp(self):
        self.case_type = 'test_case_type'
        self.app = Application.new_app('domain', 'New App', APP_V2)
        self.app.version = 3
        self.module = self.app.add_module(AdvancedModule.new_module('New Module', lang='en'))
        self.module.forms.append(AdvancedForm(name={"en": "Untitled Form"}))
        self.module.case_type = self.case_type

    def test_put_in_root(self):
        add_load_action(self.module.get_form(0), self.case_type, 'load_1')
        self.module.put_in_root = True
        self.assertFalse(self.module.form_filtering_allowed())

    def test_all_update(self):
        """
        All forms load a case and all case tags are the same
        """
        add_load_action(self.module.get_form(0), self.case_type, 'load_1')

        self.module.forms.append(AdvancedForm(name={"en": "Untitled Form 2"}))
        add_load_action(self.module.get_form(1), self.case_type, 'load_1')

        self.assertTrue(self.module.form_filtering_allowed())

    def test_not_all_update(self):
        """
        Not all forms load a case
        """
        self.module.forms.append(AdvancedForm(name={"en": "Untitled Form 2"}))
        add_load_action(self.module.get_form(1), self.case_type, 'load_1')

        self.assertFalse(self.module.form_filtering_allowed())

    def test_different_case_tags(self):
        """
        Not all case tags are the same
        """
        add_load_action(self.module.get_form(0), self.case_type, 'load_1')

        self.module.forms.append(AdvancedForm(name={"en": "Untitled Form 2"}))
        add_load_action(self.module.get_form(1), self.case_type, 'load_another_1')

        self.assertFalse(self.module.form_filtering_allowed())

    def test_auto_load(self):
        """
        Make sure we ignore auto-loaded cases
        """
        self.module.get_form(0).actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.case_type,
            case_tag='auto_load_0',
            auto_select=AutoSelectCase(mode=AUTO_SELECT_USER)
        ))
        add_load_action(self.module.get_form(0), self.case_type, 'load_1')

        self.module.forms.append(AdvancedForm(name={"en": "Untitled Form 2"}))
        add_load_action(self.module.get_form(1), self.case_type, 'load_1')

        self.assertTrue(self.module.form_filtering_allowed())
