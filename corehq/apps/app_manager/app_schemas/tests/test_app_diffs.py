from __future__ import absolute_import, unicode_literals

from django.test.testcases import SimpleTestCase, TestCase

from mock import MagicMock, patch

from corehq.apps.app_manager.app_schemas.form_metadata import (
    ADDED,
    CHANGED,
    REMOVED,
    get_app_diff,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import delete_all_apps
from corehq.apps.app_manager.xform_builder import XFormBuilder


class _BaseTestAppDiffs(object):
    def setUp(self):
        super(_BaseTestAppDiffs, self).setUp()

        self.factory1 = AppFactory()
        self.app1 = self.factory1.app
        self.factory1.new_basic_module('module_1', 'case')

        self.factory2 = AppFactory()
        self.app2 = self.factory2.app
        self.factory2.new_basic_module('module_1', 'case')

    def _add_question(self, form, options=None):
        if options is None:
            options = {'name': 'name', 'label': "Name"}
        if 'name' not in options:
            options['name'] = 'name'
        if 'label' not in options:
            options['label'] = "Name"

        builder = XFormBuilder(form.name, form.source if form.source else None)
        builder.new_question(**options)
        form.source = builder.tostring(pretty_print=True).decode('utf-8')

    def _add_question_to_group(self, form, options):
        builder = XFormBuilder(form.name, form.source if form.source else None)
        group_name = options['group']
        builder.new_group(group_name, group_name)
        builder.new_question(**options)
        form.source = builder.tostring(pretty_print=True).decode('utf-8')


@patch('corehq.apps.app_manager.app_schemas.app_case_metadata.get_case_property_description_dict',
       MagicMock(return_value={}))
class TestAppDiffs(_BaseTestAppDiffs, SimpleTestCase):

    def setUp(self):
        super(TestAppDiffs, self).setUp()
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()
        is_usercase_in_use_mock.return_value = False

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()
        super(TestAppDiffs, self).tearDown()

    def test_add_module(self):
        self.factory2.new_basic_module('module_2', 'case')
        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(second[1]['changes']['module']['type'], ADDED)
        self.assertEqual(second[1]['unique_id'], self.app2.modules[1].unique_id)

    def test_remove_module(self):
        self.factory1.new_basic_module('module_2', 'case')
        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(first[1]['changes']['module']['type'], REMOVED)
        self.assertEqual(first[1]['unique_id'], self.app1.modules[1].unique_id)

    def test_remove_then_add_module(self):
        self.factory1.new_basic_module('module_2', 'case')
        self.factory2.new_basic_module('module_3', 'case')
        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(first[1]['changes']['module']['type'], REMOVED)
        self.assertEqual(first[1]['unique_id'], self.app1.modules[1].unique_id)
        self.assertEqual(second[1]['changes']['module']['type'], ADDED)
        self.assertEqual(second[1]['unique_id'], self.app2.modules[1].unique_id)

    def test_add_form(self):
        self.factory2.new_form(self.app2.modules[0])
        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(second[0]['forms'][1]['changes']['form']['type'], ADDED)
        self.assertEqual(second[0]['forms'][1]['name'], self.app2.modules[0].forms[1].name)

    def test_change_form_name(self):
        self.app2.modules[0].forms[0].name['en'] = "a new name"
        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(first[0]['forms'][0]['changes']['name']['type'], CHANGED)
        self.assertEqual(first[0]['forms'][0]['changes']['name']['type'], CHANGED)

    def test_change_form_filter(self):
        self.app2.modules[0].forms[0].form_filter = "foo = 'bar'"
        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(first[0]['forms'][0]['changes']['form_filter']['type'], CHANGED)
        self.assertEqual(first[0]['forms'][0]['changes']['form_filter']['type'], CHANGED)

    def test_remove_form(self):
        self.factory1.new_form(self.app1.modules[0])
        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(first[0]['forms'][1]['changes']['form']['type'], REMOVED)

    def test_add_question(self):
        self._add_question(self.app2.modules[0].forms[0])
        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(second[0]['forms'][0]['questions'][0]['changes']['question']['type'], ADDED)

    def test_remove_question(self):
        self._add_question(self.app1.modules[0].forms[0])
        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(first[0]['forms'][0]['questions'][0]['changes']['question']['type'], REMOVED)

    def test_remove_then_add_question(self):
        self._add_question(self.app1.modules[0].forms[0], {'name': 'foo', 'label': 'foo'})
        self._add_question(self.app2.modules[0].forms[0], {'name': 'bar', 'label': 'bar'})
        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(first[0]['forms'][0]['questions'][0]['changes']['question']['type'], REMOVED)
        self.assertEqual(second[0]['forms'][0]['questions'][0]['changes']['question']['type'], ADDED)

    def test_change_question_label(self):
        self._add_question(self.app1.modules[0].forms[0], {'label': 'foo'})
        self._add_question(self.app2.modules[0].forms[0], {'label': 'bar'})
        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(first[0]['forms'][0]['questions'][0]['changes']['label']['type'], CHANGED)
        self.assertEqual(second[0]['forms'][0]['questions'][0]['changes']['label']['type'], CHANGED)

    def test_add_question_constraint(self):
        self._add_question(self.app1.modules[0].forms[0], {'constraint': ''})
        self._add_question(self.app2.modules[0].forms[0], {'constraint': 'foo = bar'})
        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(second[0]['forms'][0]['questions'][0]['changes']['constraint']['type'], ADDED)

    def test_change_question_constraint(self):
        self._add_question(self.app1.modules[0].forms[0], {'constraint': 'foo = bar'})
        self._add_question(self.app2.modules[0].forms[0], {'constraint': 'foo != bar'})
        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(first[0]['forms'][0]['questions'][0]['changes']['constraint']['type'], CHANGED)
        self.assertEqual(second[0]['forms'][0]['questions'][0]['changes']['constraint']['type'], CHANGED)

    def test_remove_form_sets_contains_changes(self):
        self.factory1.new_form(self.app1.modules[0])
        first, second = get_app_diff(self.app1, self.app2)
        self.assertTrue(first[0]['forms'][1].changes.contains_changes)

    def test_change_question_sets_contains_changes(self):
        self._add_question(self.app1.modules[0].forms[0], {'constraint': 'foo = bar'})
        self._add_question(self.app2.modules[0].forms[0], {'constraint': 'foo != bar'})
        first, second = get_app_diff(self.app1, self.app2)

        self.assertTrue(first[0]['forms'][0].changes.contains_changes)
        self.assertTrue(second[0]['forms'][0].changes.contains_changes)

    def test_add_question_to_group(self):
        self._add_question_to_group(self.app2.modules[0].forms[0], {
            'name': 'question_in_group',
            'label': 'Q in a group',
            'group': 'agroup',
        })
        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(second[0]['forms'][0]['questions'][0]['children'][0]['changes']['question']['type'], ADDED)

    def test_remove_question_from_group(self):
        self._add_question_to_group(self.app1.modules[0].forms[0], {
            'name': 'question_in_group',
            'label': 'Q in a group',
            'group': 'agroup',
        })
        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(first[0]['forms'][0]['questions'][0]['children'][0]['changes']['question']['type'], REMOVED)

    def test_change_question_in_group(self):
        self._add_question_to_group(self.app1.modules[0].forms[0], {
            'name': 'question_in_group',
            'label': 'Q in a group',
            'group': 'agroup',
        })
        self._add_question_to_group(self.app2.modules[0].forms[0], {
            'name': 'question_in_group',
            'label': 'Foo in a group',
            'group': 'agroup'
        })
        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(second[0]['forms'][0]['questions'][0]['children'][0]['changes']['label']['type'], CHANGED)


class TestAppDiffsWithDB(_BaseTestAppDiffs, TestCase):
    def tearDown(self):
        delete_all_apps()
        super(TestAppDiffsWithDB, self).tearDown()

    def test_remove_save_property(self):
        self._add_question(self.app1.modules[0].forms[0])
        self._add_question(self.app2.modules[0].forms[0])
        self.factory1.form_requires_case(self.app1.modules[0].forms[0], update={'foo': '/data/name'})
        self.app1.save()

        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(
            first[0]['forms'][0]['questions'][0]['changes']['save_properties']['case']['foo']['type'],
            REMOVED
        )

    def test_change_save_property(self):
        self._add_question(self.app1.modules[0].forms[0])
        self._add_question(self.app2.modules[0].forms[0])
        self.factory1.form_requires_case(self.app1.modules[0].forms[0], update={'foo': '/data/name'})
        self.factory2.form_requires_case(self.app2.modules[0].forms[0], update={'bar': '/data/name'})
        self.app1.save()
        self.app2.save()

        first, second = get_app_diff(self.app1, self.app2)
        self.assertEqual(
            first[0]['forms'][0]['questions'][0]['changes']['save_properties']['case']['foo']['type'],
            REMOVED,
        )
        self.assertEqual(
            second[0]['forms'][0]['questions'][0]['changes']['save_properties']['case']['bar']['type'],
            ADDED,
        )
