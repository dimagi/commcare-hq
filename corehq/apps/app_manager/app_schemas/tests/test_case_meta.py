from __future__ import absolute_import
from __future__ import unicode_literals

import uuid

from django.test.testcases import SimpleTestCase
from mock import MagicMock, patch
from nose.tools import nottest

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.app_manager.models import (
    AdvancedModule,
    AdvancedOpenCaseAction,
    Application,
    CaseIndex,
    CaseReferences,
    DetailColumn,
    LoadUpdateAction,
    Module,
    OpenCaseAction,
    OpenSubCaseAction,
    ParentSelect,
)
from corehq.apps.app_manager.tests.util import TestXmlMixin


@patch('corehq.apps.app_manager.app_schemas.app_case_metadata.get_case_property_description_dict',
       MagicMock(return_value={}))
class CaseMetaTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'case_meta')

    def setUp(self):
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()

    def _make_module(self, app, module_id, case_type):
        m = app.add_module(Module.new_module('Module{}'.format(module_id), lang='en'))
        m.case_type = case_type
        mf = app.new_form(module_id, 'form {}'.format(case_type), lang='en',
                          attachment=self.get_xml('standard_questions').decode('utf-8'))
        mf.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
        mf.actions.open_case.condition.type = 'always'
        return m

    def _assert_properties(self, meta, property_set):
        self.assertEqual(1, len(meta.case_types))
        self.assertEqual(set(p.name for p in meta.case_types[0].properties), property_set)

    @nottest
    def get_test_app(self):
        app = Application.new_app('domain', 'New App')
        app._id = uuid.uuid4().hex
        app.version = 1
        m0 = self._make_module(app, 0, 'parent')
        m0.get_form(0).actions.subcases.extend([
            OpenSubCaseAction(case_type='child', reference_id='parent'),
            OpenSubCaseAction(case_type='other_child', reference_id='parent')
        ])
        m1 = self._make_module(app, 1, 'child')
        m1.get_form(0).actions.subcases.append(OpenSubCaseAction(
            case_type='grand child',
            reference_id='parent'
        ))
        m2 = self._make_module(app, 2, 'grand child')

        m3 = app.add_module(AdvancedModule.new_module('Module3', lang='en'))
        m3.case_type = 'other grand child'
        m3f0 = m3.new_form('other form', 'en')
        m3f0.actions.load_update_cases.append(LoadUpdateAction(
            case_type='child',
            case_tag='child'))
        m3f0.actions.open_cases.append(AdvancedOpenCaseAction(
            name_path='/data/question1',
            case_type='other grand child',
            case_indices=[CaseIndex(tag='child', reference_id='father')]
        ))
        m3f0.actions.open_cases[0].open_condition.type = 'always'

        m4 = app.add_module(AdvancedModule.new_module('Module4', lang='en'))
        m4.case_type = 'extension'
        self._make_module(app, 5, 'other_child')

        m4f0 = m4.new_form('other form', 'en')
        m4f0.actions.load_update_cases.extend([
            LoadUpdateAction(case_type='child', case_tag='child'),
            LoadUpdateAction(case_type='other_child', case_tag='other_child'),
        ])
        m4f0.actions.open_cases.extend([
            AdvancedOpenCaseAction(
                name_path='/data/question1',
                case_type='extension',
                case_indices=[CaseIndex(tag='child', relationship='extension', reference_id='host')]
            ),
            AdvancedOpenCaseAction(  # 'extension' case has 2 parents
                name_path='/data/question1',
                case_type='extension',
                case_indices=[CaseIndex(tag='other_child', relationship='extension', reference_id='host')]
            )
        ])
        m4f0.actions.open_cases[0].open_condition.type = 'always'
        m4f0.actions.open_cases[1].open_condition.type = 'always'

        m2.parent_select = ParentSelect(active=True, module_id=m1.unique_id)
        m1.parent_select = ParentSelect(active=True, module_id=m0.unique_id)

        return app

    def test_case_properties(self):
        app = Application.new_app('domain', 'New App')
        app._id = uuid.uuid4().hex
        app.version = 1
        m0 = self._make_module(app, 0, 'normal_module')
        m0f1 = m0.new_form('update case', 'en', attachment=self.get_xml('standard_questions').decode('utf-8'))
        self._assert_properties(app.get_case_metadata(), {'name'})

        m0f1.actions.update_case.condition.type = 'always'
        m0f1.actions.update_case.update = {
            "p1": "/data/question1",
            "p2": "/data/question2"
        }
        app.version = 2
        self._assert_properties(app.get_case_metadata(), {'name', 'p1', 'p2'})

    def test_case_references(self):
        app = Application.new_app('domain', 'New App')
        app._id = uuid.uuid4().hex
        app.version = 1
        m0 = self._make_module(app, 0, 'household')
        m0f1 = m0.new_form('save to case', 'en', attachment=self.get_xml('standard_questions').decode('utf-8'))
        m0f1.case_references = CaseReferences.wrap({
            'save': {
                "/data/question1": {
                    "case_type": "household",
                    "properties": [
                        "save_to_case_p1",
                        "save_to_case_p2"
                    ],
                }
            }
        })
        meta = app.get_case_metadata()
        self._assert_properties(meta, {'name', 'save_to_case_p1', 'save_to_case_p2'})
        self.assertEqual(
            meta.get_type('household').get_save_properties(m0f1.unique_id, '/data/question1'),
            ['save_to_case_p1', 'save_to_case_p2']
        )

    def test_case_references_advanced(self):
        app = Application.new_app('domain', 'New App')
        app._id = uuid.uuid4().hex
        app.version = 1
        m0 = app.add_module(AdvancedModule.new_module('Module3', lang='en'))
        m0.case_type = 'household_advanced'
        m0f1 = m0.new_form('save to case', 'en', attachment=self.get_xml('standard_questions').decode('utf-8'))
        m0f1.case_references = CaseReferences.wrap({
            'save': {
                "/data/question1": {
                    "case_type": "household_advanced",
                    "properties": [
                        "save_to_case_p1",
                        "save_to_case_p2"
                    ],
                }
            }
        })
        self._assert_properties(app.get_case_metadata(), {'name', 'save_to_case_p1', 'save_to_case_p2'})

    def test_case_references_open_close(self):
        app = Application.new_app('domain', 'New App')
        app._id = uuid.uuid4().hex
        app.version = 1
        m0 = self._make_module(app, 0, 'household')
        m0f1 = m0.new_form('save to case', 'en', attachment=self.get_xml('standard_questions').decode('utf-8'))
        m0f1.case_references = CaseReferences.wrap({
            'save': {
                "/data/question1": {
                    "case_type": "save_to_case",
                }
            }
        })
        meta_type = app.get_case_metadata().get_type('save_to_case')
        self.assertEqual({}, meta_type.opened_by)
        self.assertEqual({}, meta_type.closed_by)

        m0f1.case_references = CaseReferences.wrap({
            'save': {
                "/data/question1": {
                    "case_type": "save_to_case",
                    "create": True
                }
            }
        })
        app.version = 2
        meta_type = app.get_case_metadata().get_type('save_to_case')
        self.assertTrue(m0f1.unique_id in meta_type.opened_by)
        self.assertEqual({}, meta_type.closed_by)

        m0f1.case_references = CaseReferences.wrap({
            'save': {
                "/data/question1": {
                    "case_type": "save_to_case",
                    "close": True
                }
            }
        })
        app.version = 3
        meta_type = app.get_case_metadata().get_type('save_to_case')
        self.assertEqual({}, meta_type.opened_by)
        self.assertTrue(m0f1.unique_id in meta_type.closed_by)

    def test_non_existant_parent(self):
        """If you reference a parent property in the case list but the case type has no parent, we should tell you
        """
        app = self.get_test_app()
        app.modules[0].case_details.short.columns = [
            DetailColumn(
                header={'en': 'Parent prop reference'},
                model='case',
                field='parent/doesnt_exist',
                format='plain',
                case_tile_field='header'
            ),
        ]
        metadata = app.get_case_metadata()
        prop = metadata.get_type('parent').get_property('parent/doesnt_exist', allow_parent=True)
        self.assertIsNotNone(prop.short_details[0].error)

    def test_calculate_conditions_no_errors(self):
        """If you have a calculate condition in your case detail, you are on your own.
        """
        calculation = "instance('casedb')/casedb/case[@case_id = instance('commcaresession')]/session/case_id"
        app = self.get_test_app()
        app.modules[0].case_details.short.columns = [
            DetailColumn(
                header={'en': 'Calculate'},
                model='case',
                useXpathExpression=True,
                field="instance('casedb')/casedb/case[@case_id = instance('commcaresession')]/session/case_id",
                format='calculate',
                case_tile_field='header'
            ),
        ]
        metadata = app.get_case_metadata()
        prop = metadata.get_type('parent').get_property(calculation, allow_parent=True)
        self.assertIsNone(prop.short_details[0].error)

    def test_multiple_parents_case_lists(self):
        """If the case has multiple parents, and you reference a parent property in the
        case list, we can't tell which parent will be shown """
        app = self.get_test_app()
        # module 1 has case type 'child' which has a single parent, 'parent'
        app.modules[1].case_details.short.columns = [
            DetailColumn(
                header={'en': 'Parent prop reference'},
                model='case',
                field='parent/from_child',
                format='plain',
                case_tile_field='header'
            ),
        ]

        # module 4 has type "extension" which has 2 relationships with the
        # reference 'host': 'child' and 'other_child'
        app.modules[4].case_details.short.columns = [
            DetailColumn(
                header={'en': 'Parent prop reference'},
                model='case',
                field='host/parent_property_reference',
                format='plain',
                case_tile_field='header'
            ),
        ]

        metadata = app.get_case_metadata()
        self.assertEqual(
            (metadata
             .get_type('parent')
             .get_property('from_child')
             .short_details[0].module_id),
            app.modules[1].unique_id
        )

        for type_ in ('other_child', 'child'):
            self.assertEqual(
                (metadata
                 .get_type(type_)
                 .get_property('parent_property_reference')
                 .short_details[0].module_id),
                app.modules[4].unique_id
            )

    def test_non_case_props(self):
        """We have special syntax in case lists and case details which should be hidden or shown for the usercase
        """
        app = self.get_test_app()
        app.modules[0].case_details.short.columns = [
            DetailColumn(
                header={'en': 'Owner Name'},
                model='case',
                field='#owner_name',
                format='plain',
                case_tile_field='header'
            ),
            DetailColumn(
                header={'en': 'Username'},
                model='case',
                field='user/username',
                format='plain',
                case_tile_field='header'
            ),
        ]
        metadata = app.get_case_metadata()
        prop = metadata.get_type('parent').get_property('#owner_name')
        self.assertFalse(prop.short_details)
        self.assertFalse(prop.long_details)

        # user properties should be shown under the usercase type
        prop = metadata.get_type(USERCASE_TYPE).get_property('username')
        self.assertTrue(prop.short_details)
        self.assertFalse(prop.long_details)
