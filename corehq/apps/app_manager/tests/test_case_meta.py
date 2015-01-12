from django.test.testcases import SimpleTestCase
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module, OpenCaseAction, ParentSelect, OpenSubCaseAction, \
    AdvancedModule, LoadUpdateAction, AdvancedOpenCaseAction


class CaseMetaTest(SimpleTestCase):
    def _make_module(self, app, module_id, case_type):
        m = app.add_module(Module.new_module('Module{}'.format(module_id), lang='en'))
        m.case_type = case_type
        mf = app.new_form(module_id, 'form {}'.format(case_type), lang='en')
        mf.actions.open_case = OpenCaseAction(name_path="/data/question1", external_id=None)
        mf.actions.open_case.condition.type = 'always'
        return m

    def test_hierarchy(self):
        app = Application.new_app('domain', 'New App', APP_V2)
        m0 = self._make_module(app, 0, 'parent')
        m0.get_form(0).actions.subcases.append(OpenSubCaseAction(case_type='child'))
        m1 = self._make_module(app, 1, 'child')
        m1.get_form(0).actions.subcases.append(OpenSubCaseAction(case_type='grand child'))
        m2 = self._make_module(app, 1, 'grand child')

        m3 = app.add_module(AdvancedModule.new_module('Module3', lang='en'))
        m3.case_type = 'other grand child'
        m3f0 = m3.new_form('other form', 'en')
        m3f0.actions.load_update_cases.append(LoadUpdateAction(
            case_type='child',
            case_tag='child'))
        m3f0.actions.open_cases.append(AdvancedOpenCaseAction(
            name_path='/data/question1',
            case_type='other grand child',
            parent_tag='child'
        ))
        m3f0.actions.open_cases[0].open_condition.type = 'always'

        m2.parent_select = ParentSelect(active=True, module_id=m1.unique_id)
        m1.parent_select = ParentSelect(active=True, module_id=m0.unique_id)

        meta = app.get_case_metadata()
        self.assertDictEqual(meta.type_hierarchy, {
            'parent': {
                'child': {
                    'grand child': {},
                    'other grand child': {}
                }}})
