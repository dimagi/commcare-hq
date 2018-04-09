from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from django.test.testcases import SimpleTestCase
from mock import patch, MagicMock
from nose.tools import nottest

from corehq.apps.app_manager.models import Application, Module, OpenCaseAction, ParentSelect, OpenSubCaseAction, \
    AdvancedModule, LoadUpdateAction, AdvancedOpenCaseAction, CaseIndex, CaseReferences
from corehq.apps.app_manager.tests.util import TestXmlMixin


@patch('corehq.apps.app_manager.models.get_case_property_description_dict', MagicMock(return_value={}))
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
                          attachment=self.get_xml('standard_questions'))
        mf.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
        mf.actions.open_case.condition.type = 'always'
        return m

    def _assert_properties(self, meta, property_set):
        self.assertEqual(1, len(meta.case_types))
        self.assertEqual(set(p.name for p in meta.case_types[0].properties), property_set)

    def test_hierarchy(self):
        app, expected_hierarchy = self.get_test_app()
        meta = app.get_case_metadata()
        self.assertDictEqual(meta.type_hierarchy, expected_hierarchy)

    @nottest
    def get_test_app(self):
        app = Application.new_app('domain', 'New App')
        app._id = uuid.uuid4().hex
        app.version = 1
        m0 = self._make_module(app, 0, 'parent')
        m0.get_form(0).actions.subcases.append(OpenSubCaseAction(
            case_type='child',
            reference_id='parent'
        ))
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
            case_indices=[CaseIndex(tag='child')]
        ))
        m3f0.actions.open_cases[0].open_condition.type = 'always'

        m2.parent_select = ParentSelect(active=True, module_id=m1.unique_id)
        m1.parent_select = ParentSelect(active=True, module_id=m0.unique_id)

        expected_hierarchy = {
            'parent': {
                'child': {
                    'grand child': {},
                    'other grand child': {}
                }
            }
        }
        return app, expected_hierarchy

    def test_case_properties(self):
        app = Application.new_app('domain', 'New App')
        app._id = uuid.uuid4().hex
        app.version = 1
        m0 = self._make_module(app, 0, 'normal_module')
        m0f1 = m0.new_form('update case', 'en', attachment=self.get_xml('standard_questions'))
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
        m0f1 = m0.new_form('save to case', 'en', attachment=self.get_xml('standard_questions'))
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
        self._assert_properties(app.get_case_metadata(), {'name', 'save_to_case_p1', 'save_to_case_p2'})

    def test_case_references_advanced(self):
        app = Application.new_app('domain', 'New App')
        app._id = uuid.uuid4().hex
        app.version = 1
        m0 = app.add_module(AdvancedModule.new_module('Module3', lang='en'))
        m0.case_type = 'household_advanced'
        m0f1 = m0.new_form('save to case', 'en', attachment=self.get_xml('standard_questions'))
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
        self._assert_properties(app.get_case_metadata(), {'save_to_case_p1', 'save_to_case_p2'})

    def test_case_references_open_close(self):
        app = Application.new_app('domain', 'New App')
        app._id = uuid.uuid4().hex
        app.version = 1
        m0 = self._make_module(app, 0, 'household')
        m0f1 = m0.new_form('save to case', 'en', attachment=self.get_xml('standard_questions'))
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
