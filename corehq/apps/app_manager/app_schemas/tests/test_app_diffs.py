from __future__ import absolute_import, unicode_literals

from django.test.testcases import SimpleTestCase

from mock import MagicMock, patch

from corehq.apps.app_manager.app_schemas.form_metadata import (
    ADDED,
    CHANGED,
    REMOVED,
    get_app_diff,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.xform_builder import XFormBuilder


@patch('corehq.apps.app_manager.app_schemas.app_case_metadata.get_case_property_description_dict',
       MagicMock(return_value={}))
class TestAppDiffs(SimpleTestCase):

    def setUp(self):
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()
        is_usercase_in_use_mock.return_value = False

        self.factory1 = AppFactory()
        self.app1 = self.factory1.app
        self.factory1.new_basic_module('module_1', 'case')

        self.factory2 = AppFactory()
        self.app2 = self.factory2.app
        self.factory2.new_basic_module('module_1', 'case')

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()

    def test_add_module(self):
        self.factory2.new_basic_module('module_2', 'case')
        diff = get_app_diff(self.app1, self.app2)
        self.assertEqual(diff.second[1]['diff_state'], ADDED)
        self.assertEqual(diff.second[1]['id'], self.app2.modules[1].unique_id)

    def test_remove_module(self):
        self.factory1.new_basic_module('module_2', 'case')
        diff = get_app_diff(self.app1, self.app2)
        self.assertEqual(diff.first[1]['diff_state'], REMOVED)
        self.assertEqual(diff.first[1]['id'], self.app1.modules[1].unique_id)

    def test_remove_then_add_module(self):
        self.factory1.new_basic_module('module_2', 'case')
        self.factory2.new_basic_module('module_3', 'case')
        diff = get_app_diff(self.app1, self.app2)
        self.assertEqual(diff.first[1]['diff_state'], REMOVED)
        self.assertEqual(diff.first[1]['id'], self.app1.modules[1].unique_id)
        self.assertEqual(diff.second[1]['diff_state'], ADDED)
        self.assertEqual(diff.second[1]['id'], self.app2.modules[1].unique_id)

    def test_add_form(self):
        self.factory2.new_form(self.app2.modules[0])
        diff = get_app_diff(self.app1, self.app2)
        self.assertEqual(diff.second[0]['forms'][1]['diff_state'], ADDED)
        self.assertEqual(diff.second[0]['forms'][1]['name'], self.app2.modules[0].forms[1].name)

    def test_remove_form(self):
        self.factory1.new_form(self.app1.modules[0])
        diff = get_app_diff(self.app1, self.app2)
        self.assertEqual(diff.first[0]['forms'][1]['diff_state'], REMOVED)

    def _add_question(self, form, options=None):
        if options is None:
            options = {'name': 'name', 'label': "Name"}
        if 'name' not in options:
            options['name'] = 'name'
        if 'label' not in options:
            options['label'] = "Name"

        builder = XFormBuilder(form.name)
        builder.new_question(**options)
        form.source = builder.tostring(pretty_print=True).decode('utf-8')

    def test_add_question(self):
        self._add_question(self.app2.modules[0].forms[0])
        diff = get_app_diff(self.app1, self.app2)
        self.assertEqual(diff.second[0]['forms'][0]['questions'][0]['diff_state'], ADDED)

    def test_remove_question(self):
        self._add_question(self.app1.modules[0].forms[0])
        diff = get_app_diff(self.app1, self.app2)
        self.assertEqual(diff.first[0]['forms'][0]['questions'][0]['diff_state'], REMOVED)

    def test_remove_then_add_question(self):
        self._add_question(self.app1.modules[0].forms[0], {'name': 'foo', 'label': 'foo'})
        self._add_question(self.app2.modules[0].forms[0], {'name': 'bar', 'label': 'bar'})
        diff = get_app_diff(self.app1, self.app2)
        self.assertEqual(diff.first[0]['forms'][0]['questions'][0]['diff_state'], REMOVED)
        self.assertEqual(diff.second[0]['forms'][0]['questions'][0]['diff_state'], ADDED)

    def test_change_question_label(self):
        self._add_question(self.app1.modules[0].forms[0], {'label': 'foo'})
        self._add_question(self.app2.modules[0].forms[0], {'label': 'bar'})
        diff = get_app_diff(self.app1, self.app2)
        self.assertEqual(diff.first[0]['forms'][0]['questions'][0]['diff_state'], CHANGED)
        self.assertEqual(diff.first[0]['forms'][0]['questions'][0]['diff_attribute'], 'label')
        self.assertEqual(diff.second[0]['forms'][0]['questions'][0]['diff_state'], CHANGED)
        self.assertEqual(diff.second[0]['forms'][0]['questions'][0]['diff_attribute'], 'label')

    def test_add_question_display_condition(self):
        self._add_question(self.app1.modules[0].forms[0], {'constraint': ''})
        self._add_question(self.app2.modules[0].forms[0], {'constraint': 'foo = bar'})
        diff = get_app_diff(self.app1, self.app2)
        self.assertEqual(diff.second[0]['forms'][0]['questions'][0]['diff_state'], ADDED)
        self.assertEqual(diff.second[0]['forms'][0]['questions'][0]['diff_attribute'], 'constraint')

    def test_change_question_display_condition(self):
        self._add_question(self.app1.modules[0].forms[0], {'constraint': 'foo = bar'})
        self._add_question(self.app2.modules[0].forms[0], {'constraint': 'foo != bar'})
        diff = get_app_diff(self.app1, self.app2)
        self.assertEqual(diff.first[0]['forms'][0]['questions'][0]['diff_state'], CHANGED)
        self.assertEqual(diff.first[0]['forms'][0]['questions'][0]['diff_attribute'], 'constraint')
        self.assertEqual(diff.second[0]['forms'][0]['questions'][0]['diff_state'], CHANGED)
        self.assertEqual(diff.second[0]['forms'][0]['questions'][0]['diff_attribute'], 'constraint')
