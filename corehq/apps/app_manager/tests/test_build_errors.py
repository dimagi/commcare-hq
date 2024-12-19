import json
import os
from unittest.mock import patch

from django.test import TestCase

from corehq import privileges
from corehq.apps.app_manager.const import (
    REGISTRY_WORKFLOW_LOAD_CASE,
    REGISTRY_WORKFLOW_SMART_LINK,
    WORKFLOW_FORM,
    WORKFLOW_MODULE,
)
from corehq.apps.app_manager.models import (
    Application,
    CaseList,
    CaseSearch,
    CaseSearchLabel,
    CaseSearchProperty,
    DetailColumn,
    DetailTab,
    FormLink,
    Module,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.util.test_utils import flag_enabled, privilege_enabled


@patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
@patch('corehq.apps.app_manager.helpers.validators.domain_has_privilege', return_value=True)
class BuildErrorsTest(TestCase):

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

    def test_dof_session_endpoint_error(self, *args):
        factory = AppFactory(build_version='2.51.0')
        app = factory.app
        m0 = factory.new_basic_module('first', 'case', with_form=False)
        m0.put_in_root = True
        m0.session_endpoint_id = "this_is_m0"
        m1 = factory.new_basic_module('second', 'case', with_form=False)
        m1.session_endpoint_id = "this_is_m1"

        with patch.object(Application, 'enable_practice_users', return_value=False):    # avoid db
            errors = app.validate_app()

        self._clean_unique_id(errors)
        self.assertEqual(len(errors), 3)
        self.assertIn({
            'type': 'endpoint to display only forms',
            'module': {'id': 0, 'name': {'en': 'first module'}},
        }, errors)
        self.assertIn({
            'type': 'no forms or case list',
            'module': {'id': 0, 'name': {'en': 'first module'}},
        }, errors)
        self.assertIn({
            'type': 'no forms or case list',
            'module': {'id': 1, 'name': {'en': 'second module'}},
        }, errors)

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

    def test_case_tile_mapping_errors(self, *args):
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

    def test_case_tile_case_detail(self, *args):
        case_tile_error = {
            'type': 'invalid tile configuration',
            'module': {'id': 0, 'name': {'en': 'Add Song module'}},
            'reason': 'Case tiles on the case detail must be manually configured.',
        }
        factory = AppFactory(build_version='2.51.0')
        app = factory.app
        module = factory.new_basic_module('Add Song', 'song', with_form=False)
        module.case_details.long.case_tile_template = "one_3X_two_4X_one_2X"
        module.case_details.long.columns.append(DetailColumn(
            format='plain',
            field='artist',
            header={'en': 'Artist'},
        ))

        errors = app.validate_app()
        self._clean_unique_id(errors)
        self.assertIn(case_tile_error, errors)

        module.case_details.long.case_tile_template = "custom"
        errors = app.validate_app()
        self._clean_unique_id(errors)
        self.assertNotIn(case_tile_error, errors)

    def test_case_tile_case_detail_tabs(self, *args):
        case_tile_error = {
            'type': 'invalid tile configuration',
            'module': {'id': 0, 'name': {'en': 'Add Song module'}},
            'reason': 'Each row of the tile may contain fields only from a single tab. '
                      'Row #1 contains fields from multiple tabs.'
        }
        factory = AppFactory(build_version='2.51.0')
        app = factory.app
        module = factory.new_basic_module('Add Song', 'song', with_form=False)
        module.case_details.long.case_tile_template = "custom"

        # Start with a legitimate tab+column layout
        module.case_details.long.tabs = [
            DetailTab(starting_index=0),
            DetailTab(starting_index=2),
        ]
        module.case_details.long.columns = []
        module.case_details.long.columns.append(DetailColumn(
            format='plain',
            field='artist', header={'en': 'Artist'},
            grid_x=0, grid_y=0, width=4, height=1,
        ))
        module.case_details.long.columns.append(DetailColumn(
            format='plain',
            field='name', header={'en': 'Name'},
            grid_x=5, grid_y=0, width=4, height=1,
        ))
        module.case_details.long.columns.append(DetailColumn(
            format='plain',
            field='mood', header={'en': 'Mood'},
            grid_x=0, grid_y=1, width=4, height=1,
        ))
        module.case_details.long.columns.append(DetailColumn(
            format='plain',
            field='energy', header={'en': 'Energy'},
            grid_x=5, grid_y=1, width=4, height=1,
        ))

        module.case_details.long_case_tile_template = "custom"
        errors = app.validate_app()
        self._clean_unique_id(errors)
        self.assertNotIn(case_tile_error, errors)

        # Move field from second tab into first row of tile
        module.case_details.long.columns[2].grid_y = 0
        module.case_details.long.columns[2].grid_x = 9

        errors = app.validate_app()
        self._clean_unique_id(errors)
        self.assertIn(case_tile_error, errors)

    def create_app_with_module(self):
        factory = AppFactory(build_version='2.51.0')
        app = factory.app
        module = factory.new_basic_module('first', 'case', with_form=False)

        return app, module

    def test_clickable_icon_configuration_errors(self, *args):
        case_tile_error = {
            'type': "invalid clickable icon configuration",
            'module': {'id': 0, 'name': {'en': 'first module'}},
            'reason': 'Column/Field "field": Clickable Icons require a form to be configured.'
        }
        app, module = self.create_app_with_module()

        module.case_details.short.columns.append(DetailColumn(
            format='clickable-icon',
            field='field',
            header={'en': 'Column'},
            model='case',
        ))

        errors = app.validate_app()
        self._clean_unique_id(errors)
        self.assertIn(case_tile_error, errors)

    def test_address_popup_defined_in_case_list(self, *args):
        case_tile_error = {
            'type': "deprecated popup configuration",
            'module': {'id': 0, 'name': {'en': 'first module'}},
            'reason': 'Format "Address Popup" should be used in the Case Detail not Case List.'
        }
        app, module = self.create_app_with_module()
        module.case_details.short.columns.append(DetailColumn(
            format='address-popup',
            field='field',
            header={'en': 'Column'},
            model='case',
        ))

        errors = app.validate_app()
        self._clean_unique_id(errors)
        self.assertIn(case_tile_error, errors)

    def test_address__defined_twice(self, *args):
        case_tile_error = {
            'type': "invalid tile configuration",
            'module': {'id': 0, 'name': {'en': 'first module'}},
            'reason': 'Format "Address" can only be used once but is used by multiple properties: "f1", "f2"'
        }
        app, module = self.create_app_with_module()
        for field_id in [1, 2]:
            module.case_details.short.columns.append(DetailColumn(
                format='address',
                field=f'f{field_id}',
                header={'en': 'Column'},
                model='case',
            ))

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

    @flag_enabled('DATA_REGISTRY')
    @patch.object(Application, 'supports_data_registry', lambda: True)
    def test_multi_select_module_errors(self, *args):
        factory = AppFactory()
        module, form = factory.new_basic_module('basic', 'person')
        factory.form_requires_case(form, 'person')

        module.case_details.short.multi_select = True
        module.search_config = CaseSearch(
            search_label=CaseSearchLabel(label={'en': 'Search'}),
            properties=[CaseSearchProperty(name=field) for field in ['name', 'greatest_fear']],
            data_registry="so_many_cases",
            data_registry_workflow=REGISTRY_WORKFLOW_LOAD_CASE,
        )

        self.assertIn({
            'type': 'data registry multi select',
            'module': {'id': 0, 'unique_id': 'basic_module', 'name': {'en': 'basic module'}}
        }, factory.app.validate_app())

        module.search_config.data_registry_workflow = REGISTRY_WORKFLOW_SMART_LINK
        self.assertIn({
            'type': 'smart links multi select',
            'module': {'id': 0, 'unique_id': 'basic_module', 'name': {'en': 'basic module'}}
        }, factory.app.validate_app())

    def test_search_module_errors_instances(self, *args):
        factory = AppFactory()
        module, form = factory.new_basic_module('basic', 'person')
        factory.form_requires_case(form, 'person')

        module.case_details.long.columns.extend([
            DetailColumn.wrap(dict(
                header={"en": "name"},
                model="case",
                format="plain",
                useXpathExpression=True,
                field="instance('results')/results",
            )),
            DetailColumn.wrap(dict(
                header={"en": "age"},
                model="case",
                format="plain",
                useXpathExpression=True,
                field="instance('search-input:results')/input",
            ))
        ])
        module.search_config = CaseSearch(
            search_label=CaseSearchLabel(label={'en': 'Search'}),
            properties=[CaseSearchProperty(name='name')],
        )

        errors = [(error['type'], error.get('details', '')) for error in factory.app.validate_app()]
        self.assertIn(('case search instance used in casedb case details', 'results'), errors)
        self.assertIn(('case search instance used in casedb case details', 'search-input:results'), errors)

        module.search_config.auto_launch = True
        self.assertNotIn(
            'case search instance used in casedb case details',
            [error['type'] for error in factory.app.validate_app()]
        )

    def test_form_module_validation(self, *args):
        factory = AppFactory(build_version='2.24.0')
        app = factory.app
        m0, m0f0 = factory.new_basic_module('register', 'case')

        m0f0.post_form_workflow = WORKFLOW_MODULE

        m1 = factory.new_shadow_module('shadow', m0, with_form=False)
        m1.put_in_root = True

        errors = app.validate_app()

        self._clean_unique_id(errors)
        self.assertIn({
            'type': 'form link to display only forms',
            'form_type': 'module_form',
            'module': {'id': 1, 'name': {'en': 'shadow module'}},
            'form': {'id': 0, 'name': {'en': 'register form 0'}},
        }, errors)

    @privilege_enabled(privileges.FORM_LINK_WORKFLOW)
    def test_form_link_validation_ok(self, *args):
        factory = AppFactory(build_version='2.24.0', include_xmlns=True)
        m0, m0f0 = factory.new_basic_module('m0', 'frog')
        m1, m1f0 = factory.new_basic_module('m1', 'frog')

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="true()", form_id=m1f0.unique_id, form_module_id=m1.unique_id),
            FormLink(xpath="true()", form_id=m1f0.unique_id)  # legacy data
        ]

        errors = factory.app.validate_app()
        self.assertNotIn('bad form link', [error['type'] for error in errors])

    @privilege_enabled(privileges.FORM_LINK_WORKFLOW)
    def test_form_link_validation_mismatched_module(self, *args):
        factory = AppFactory(build_version='2.24.0', include_xmlns=True)
        m0, m0f0 = factory.new_basic_module('m0', 'frog')
        m1, m1f0 = factory.new_basic_module('m1', 'frog')

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="true()", form_id=m1f0.unique_id, form_module_id=m0.unique_id)
        ]

        errors = factory.app.validate_app()

        self._clean_unique_id(errors)
        self.assertIn({
            'type': 'bad form link',
            'form_type': 'module_form',
            'module': {'id': 0, 'name': {'en': 'm0 module'}},
            'form': {'id': 0, 'name': {'en': 'm0 form 0'}},
        }, errors)

    @privilege_enabled(privileges.FORM_LINK_WORKFLOW)
    def test_form_link_validation_shadow_module_ok(self, *args):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('parent', 'mother')
        m1, m1f0 = factory.new_basic_module('other', 'mother')
        m2 = factory.new_shadow_module('shadow_module', m1, with_form=False)

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath='true()', form_id=m1f0.unique_id, form_module_id=m1.unique_id),
            FormLink(xpath='true()', form_id=m1f0.unique_id, form_module_id=m2.unique_id),
        ]

        errors = factory.app.validate_app()
        self.assertNotIn('bad form link', [error['type'] for error in errors])

    @privilege_enabled(privileges.FORM_LINK_WORKFLOW)
    def test_form_link_validation_mismatched_shadow_module(self, *args):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('m0', 'mother')
        m1, m1f0 = factory.new_basic_module('m1', 'mother')
        factory.new_shadow_module('shadow_module', m1, with_form=False)

        # link from m0-f0 to m1-f0 (in the shadow module)
        m0f0.post_form_workflow = WORKFLOW_FORM
        # module_id is incorrect - it should be either m1 or m2 but not m0
        m0f0.form_links = [FormLink(xpath='true()', form_id=m1f0.unique_id, form_module_id=m0.unique_id)]

        errors = factory.app.validate_app()

        self._clean_unique_id(errors)
        self.assertIn({
            'type': 'bad form link',
            'form_type': 'module_form',
            'module': {'id': 0, 'name': {'en': 'm0 module'}},
            'form': {'id': 0, 'name': {'en': 'm0 form 0'}},
        }, errors)

    @patch('corehq.apps.app_manager.models.ModuleBase.is_auto_select', return_value=True)
    def test_search_on_clear_with_auto_select(self, *args):
        factory = AppFactory()
        module = factory.new_basic_module('basic', 'person', with_form=False)
        module.search_config = CaseSearch(
            search_on_clear=True,
        )
        errors = factory.app.validate_app()
        self.assertIn({
            'type': 'search on clear with auto select',
            'module': {'id': 0, 'unique_id': 'basic_module', 'name': {'en': 'basic module'}},
        }, errors)
