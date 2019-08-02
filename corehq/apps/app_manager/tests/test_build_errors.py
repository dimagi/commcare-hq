from __future__ import absolute_import
from __future__ import unicode_literals
import json
from django.test import SimpleTestCase
import os

from mock import patch

from corehq.apps.app_manager.models import Application, CaseList, Module
from corehq.apps.app_manager.tests.app_factory import AppFactory
from io import open


@patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
@patch('corehq.apps.app_manager.helpers.validators.domain_has_privilege', return_value=True)
@patch('corehq.apps.builds.models.BuildSpec.supports_j2me', return_value=False)
class BuildErrorsTest(SimpleTestCase):

    @staticmethod
    def _clean_unique_id(errors):
        for error in errors:
            if 'form' in error and 'unique_id' in error['form']:
                del error['form']['unique_id']
            if 'module' in error and 'unique_id' in error['module']:
                del error['module']['unique_id']

    def test_subcase_errors(self, *args):
        with open(os.path.join(os.path.dirname(__file__), 'data', 'subcase-details.json'), encoding='utf-8') as f:
            source = json.load(f)

        app = Application.wrap(source)
        errors = app.validate_app()
        update_path_error = {
            'type': 'path error',
            'path': '/data/parent_age',
            'form_type': 'module_form',
            'module': {'name': {'en': "Parent"}, 'id': 0},
            'form': {'id': 0, 'name': {'en': "Register"}},
        }
        subcase_path_error = {
            'type': 'path error',
            'path': '/data/child_age',
            'form_type': 'module_form',
            'module': {'name': {'en': "Parent"}, 'id': 0},
            'form': {'id': 0, 'name': {'en': "Register"}},
        }
        self._clean_unique_id(errors)
        self.assertIn(update_path_error, errors)
        self.assertIn(subcase_path_error, errors)

        form = app.get_module(0).get_form(0)
        errors = form.validate_for_build()
        self._clean_unique_id(errors)
        self.assertIn(update_path_error, errors)
        self.assertIn(subcase_path_error, errors)

    def test_empty_module_errors(self, *args):
        factory = AppFactory(build_version='2.24.0')
        app = factory.app
        m1 = factory.new_basic_module('register', 'case', with_form=False)
        factory.new_advanced_module('update', 'case', with_form=False)

        m2 = factory.new_basic_module('update', 'case', with_form=False)
        m2.case_list = CaseList(show=True, label={'en': "case_list"})

        factory.new_shadow_module('update', m1, with_form=False)
        errors = app.validate_app()

        standard_module_error = {
            'type': 'no forms or case list',
            'module': {'id': 0, 'name': {'en': 'register module'}},
        }
        advanced_module_error = {
            'type': 'no forms or case list',
            'module': {'id': 1, 'name': {'en': 'update module'}},
        }
        self._clean_unique_id(errors)
        self.assertEqual(len(errors), 2)
        self.assertIn(standard_module_error, errors)
        self.assertIn(advanced_module_error, errors)

    def test_parent_cycle_in_app(self, *args):
        cycle_error = {
            'type': 'parent cycle',
        }

        with open(os.path.join(os.path.dirname(__file__), 'data', 'cyclical-app.json')) as f:
            source = json.load(f)

            app = Application.wrap(source)
            errors = app.validate_app()
            self._clean_unique_id(errors)
            self.assertIn(cycle_error, errors)

    def test_case_tile_configuration_errors(self, *args):
        case_tile_error = {
            'type': "invalid tile configuration",
            'module': {'id': 0, 'name': {'en': 'View'}},
            'reason': 'A case property must be assigned to the "sex" tile field.'
        }
        with open(os.path.join(
            os.path.dirname(__file__), 'data', 'bad_case_tile_config.json'
        )) as f:
            source = json.load(f)
            app = Application.wrap(source)
            errors = app.validate_app()
            self._clean_unique_id(errors)
            self.assertIn(case_tile_error, errors)

    def test_case_list_form_advanced_module_different_case_config(self, *args):
        case_tile_error = {
            'type': "all forms in case list module must load the same cases",
            'module': {'id': 1, 'name': {'en': 'update module'}},
            'form': {'id': 1, 'name': {'en': 'update form 1'}},
        }

        factory = AppFactory(build_version='2.11.0')
        m0, m0f0 = factory.new_basic_module('register', 'person')
        factory.form_opens_case(m0f0)

        m1, m1f0 = factory.new_advanced_module('update', 'person', case_list_form=m0f0)
        factory.form_requires_case(m1f0, case_type='house')
        factory.form_requires_case(m1f0, parent_case_type='house')

        m1f1 = factory.new_form(m1)
        factory.form_requires_case(m1f1)  # only loads a person case and not a house case

        errors = factory.app.validate_app()
        self._clean_unique_id(errors)
        self.assertIn(case_tile_error, errors)

    @patch('corehq.apps.app_manager.models.domain_has_privilege', return_value=True)
    def test_training_module_as_parent(self, *args):
        factory = AppFactory(build_version='2.43.0')
        app = factory.app

        training_module = Module.new_training_module('training', 'en')
        app.add_module(training_module)

        child_module, _ = factory.new_basic_module('child', 'case_type', parent_module=training_module)

        self.assertIn({
            'type': 'training module parent',
            'module': {'id': 1, 'unique_id': 'child_module', 'name': {'en': 'child module'}}
        }, app.validate_app())

    @patch('corehq.apps.app_manager.models.domain_has_privilege', return_value=True)
    def test_training_module_as_child(self, *args):
        factory = AppFactory(build_version='2.43.0')
        app = factory.app

        parent_module = Module.new_module('parent', 'en')
        app.add_module(parent_module)

        training_module, _ = factory.new_basic_module('training', 'case_type', parent_module=parent_module)
        training_module.is_training_module = True

        self.assertIn({
            'type': 'training module child',
            'module': {'id': 1, 'unique_id': 'training_module', 'name': {'en': 'training module'}}
        }, app.validate_app())
