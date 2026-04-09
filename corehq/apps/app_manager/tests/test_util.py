from django.test import SimpleTestCase, TestCase

from corehq.apps.app_manager.models import AdvancedModule, Application, Module
from corehq.apps.app_manager.tests.util import SuiteMixin
from corehq.apps.app_manager.util import (
    _save_question_to_case_name,
    does_app_have_mobile_ucr_v1_refs,
    split_path,
)
from corehq.apps.app_manager.views.utils import get_default_followup_form_xml


class TestGetDefaultFollowupForm(SimpleTestCase):
    def test_default_followup_form(self):
        app = Application.new_app('domain', "Untitled Application")

        parent_module = app.add_module(AdvancedModule.new_module('parent', None))
        parent_module.case_type = 'parent'
        parent_module.unique_id = 'id_parent_module'

        context = {
            'lang': None,
            'default_label': "Default label message"
        }
        attachment = get_default_followup_form_xml(context=context)
        followup = app.new_form(0, "Followup Form", None, attachment=attachment)

        self.assertEqual(followup.name['en'], "Followup Form")
        self.assertEqual(app.modules[0].forms[0].name['en'], "Followup Form")

        first_question = app.modules[0].forms[0].get_questions([], include_triggers=True, include_groups=True)[0]
        self.assertEqual(first_question['label'], " Default label message ")


class TestSplitPath(SimpleTestCase):

    def test_path_filename(self):
        path, name = split_path('foo/bar/baz.txt')
        self.assertEqual(path, 'foo/bar')
        self.assertEqual(name, 'baz.txt')

    def test_no_slash(self):
        path, name = split_path('foo')
        self.assertEqual(path, '')
        self.assertEqual(name, 'foo')

    def test_empty_string(self):
        path, name = split_path('')
        self.assertEqual(path, '')
        self.assertEqual(name, '')


class TestSaveQuestionToCaseName:
    LANG = 'en'

    def test_default_question_path_is_null(self):
        form = self._create_form()
        assert form.actions.open_case.name_update is not None

        _save_question_to_case_name(form, self.LANG)

        assert form.actions.open_case.name_update.question_path is None

    def _create_form(self):
        app = Application.new_app('domain', "App")
        module = app.add_module(Module.new_module('module', None))
        return module.new_form(name="Registration", lang=None)


class TestDoesAppHaveMobileUCRV1Refs(TestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def _create_app_with_form(self, xml_source_name):
        app = Application.new_app('domain', "Untitled Application")
        app.add_module(AdvancedModule.new_module('module', None))
        app.new_form(
            module_id=0,
            name="My Form",
            lang=None,
            attachment=self.get_xml(xml_source_name).decode('utf-8')
        )
        return app

    def test_does_app_have_mobile_ucr_v1_refs(self):
        app_with_refs = self._create_app_with_form('reports_module_data_entry_mobile_ucr_v1')
        self.assertTrue(does_app_have_mobile_ucr_v1_refs(app_with_refs))
        app_without_refs = self._create_app_with_form('normal-suite')
        self.assertFalse(does_app_have_mobile_ucr_v1_refs(app_without_refs))
