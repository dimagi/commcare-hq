from django.test import SimpleTestCase

from mock import patch

from corehq.apps.app_manager.const import AUTO_SELECT_USERCASE
from corehq.apps.app_manager.models import (
    AdvancedModule,
    AdvancedOpenCaseAction,
    Application,
    AutoSelectCase,
    CaseIndex,
    LoadUpdateAction,
    Module,
    ReportAppConfig,
    ReportModule,
)
from corehq.apps.app_manager.util import purge_report_from_mobile_ucr
from corehq.apps.userreports.models import ReportConfiguration
from corehq.util.test_utils import flag_enabled


class ModuleTests(SimpleTestCase):

    def setUp(self):
        self.app = Application.new_app('domain', "Untitled Application")
        self.module = self.app.add_module(Module.new_module('Untitled Module', None))
        self.module.case_type = 'another_case_type'
        self.form = self.module.new_form("Untitled Form", None)


class AdvancedModuleTests(SimpleTestCase):

    def setUp(self):
        self.app = Application.new_app('domain', "Untitled Application")
        self.module = self.app.add_module(AdvancedModule.new_module('Untitled Module', None))
        self.form = self.module.new_form("Untitled Form", None)

    def test_registration_form_simple(self):
        self.form.actions.open_cases = [
            AdvancedOpenCaseAction(
                case_tag="phone",
                case_type="phone",
                name_path="/data/question1",
            )
        ]

        self.assertTrue(self.form.is_registration_form())

    def test_registration_form_subcase(self):
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type="parent",
            case_tag="parent"
        ))
        self.form.actions.open_cases = [
            AdvancedOpenCaseAction(
                case_tag="child",
                case_type="child",
                name_path="/data/question1",
                case_indices=[CaseIndex(tag="parent")]
            )
        ]

        self.assertTrue(self.form.is_registration_form())

    def test_registration_form_autoload(self):
        self.form.actions.load_update_cases = [
            LoadUpdateAction(
                auto_select=AutoSelectCase(mode=AUTO_SELECT_USERCASE, value_key=""),
            )
        ]

        self.form.actions.open_cases = [
            AdvancedOpenCaseAction(
                case_tag="child",
                case_type="child",
                name_path="/data/question1",
            )
        ]

        self.assertTrue(self.form.is_registration_form())

    def test_registration_form_autoload_subcase(self):
        self.form.actions.load_update_cases = [
            LoadUpdateAction(
                case_type="parent",
                case_tag="parent"
            ),
            LoadUpdateAction(
                auto_select=AutoSelectCase(mode=AUTO_SELECT_USERCASE, value_key=""),
            )
        ]

        self.form.actions.open_cases = [
            AdvancedOpenCaseAction(
                case_tag="child",
                case_type="child",
                name_path="/data/question1",
                case_indices=[CaseIndex(tag="parent")]
            )
        ]

        self.assertTrue(self.form.is_registration_form())

    def test_registration_form_subcase_multiple(self):
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type="parent",
            case_tag="parent"
        ))
        self.form.actions.open_cases = [
            AdvancedOpenCaseAction(
                case_tag="child",
                case_type="child",
                name_path="/data/question1",
                case_indices=[CaseIndex(tag="parent")]
            ),
            AdvancedOpenCaseAction(
                case_tag="grandchild",
                case_type="grandchild",
                name_path="/data/children/question1",
                case_indices=[CaseIndex(tag="child")]
            )
        ]

        self.assertFalse(self.form.is_registration_form())

    def test_registration_form_subcase_multiple_repeat(self):
        self.test_registration_form_subcase_multiple()
        self.form.actions.open_cases[-1].repeat_context = "/data/children"

        self.assertTrue(self.form.is_registration_form())


class ReportModuleTests(SimpleTestCase):

    @flag_enabled('MOBILE_UCR')
    @patch('dimagi.ext.couchdbkit.Document.get_db')
    def test_purge_report_from_mobile_ucr(self, get_db):
        report_config = ReportConfiguration(domain='domain', config_id='foo1')
        report_config._id = "my_report_config"

        app = Application.new_app('domain', "App")
        report_module = app.add_module(ReportModule.new_module('Reports', None))
        report_module.report_configs = [
            ReportAppConfig(report_id=report_config._id, header={'en': 'CommBugz'}),
            ReportAppConfig(report_id='other_config_id', header={'en': 'CommBugz'})
        ]
        self.assertEqual(len(app.modules[0].report_configs), 2)

        with patch('corehq.apps.app_manager.util.get_apps_in_domain') as get_apps:
            get_apps.return_value = [app]
            # this will get called when report_config is deleted
            purge_report_from_mobile_ucr(report_config)

        self.assertEqual(len(app.modules[0].report_configs), 1)


class OverwriteModuleDetailTests(SimpleTestCase):
 
    def setUp(self):
        self.attrs_dict1 = {
        'columns': True, 
        'filter': True,
        '*': True
        }
        self.attrs_dict2 = {
        'columns': True,  
        'filter': True,
        '*': False
        }
        self.attrs_dict3 = {
        'columns': False, 
        'filter': False,
        '*': True
        }

        self.app = Application.new_app('domain', "Untitled Application")
        self.src_module = self.app.add_module(Module.new_module('Src Module', lang='en'))
        self.src_module_detail_type = getattr(self.src_module.case_details, "short")
        self.header_ = getattr(self.src_module_detail_type.columns[0],'header')
        self.header_['en'] = 'status'
        self.filter_ = setattr(self.src_module_detail_type,'filter', 'a > b')
        self.lookup_enabled = setattr(self.src_module_detail_type,'lookup_enabled', True)
    
    def test_overwrite_all(self):
        dest_module = self.app.add_module(Module.new_module('Dest Module', lang='en'))
        dest_module_detail_type = getattr(dest_module.case_details, "short")
        dest_module_detail_type.overwrite_from_module_detail(self.src_module_detail_type, self.attrs_dict1)
        self.assertEqual(self.src_module_detail_type._obj, dest_module_detail_type._obj)

    def test_overwrite_filter_column(self):
        dest_module = self.app.add_module(Module.new_module('Dest Module', lang='en'))
        dest_module_detail_type = getattr(dest_module.case_details, "short")
        dest_module_detail_type.overwrite_from_module_detail(self.src_module_detail_type, self.attrs_dict2)
    
        self.assertEqual(self.src_module_detail_type.columns, dest_module_detail_type.columns)
        self.assertEqual(self.src_module_detail_type.filter, dest_module_detail_type.filter)
        self.remove_attrs(dest_module_detail_type)
        self.assertNotEqual(self.src_module_detail_type._obj, dest_module_detail_type._obj)

    
    def test_overwrite_other_configs(self):
        dest_module = self.app.add_module(Module.new_module('Dest Module', lang='en'))
        dest_module_detail_type = getattr(dest_module.case_details, "short")
        dest_module_detail_type.overwrite_from_module_detail(self.src_module_detail_type, self.attrs_dict3)
        
        self.assertNotEqual(str(self.src_module_detail_type.columns), str(dest_module_detail_type.columns))
        self.assertNotEqual(self.src_module_detail_type.filter, dest_module_detail_type.filter)
        self.remove_attrs(dest_module_detail_type)
        self.assertEqual(self.src_module_detail_type._obj, dest_module_detail_type._obj)

    
    def remove_attrs(self, dest_module_detail_type):
        delattr(self.src_module_detail_type, 'filter')
        delattr(self.src_module_detail_type, 'columns')
        delattr(dest_module_detail_type, 'filter')
        delattr(dest_module_detail_type, 'columns')