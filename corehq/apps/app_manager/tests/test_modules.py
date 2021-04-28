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
        self.all_attrs = ['columns', 'filter', 'sort_elements', 'custom_variables', 'custom_xml',
                          'case_tile_configuration', 'print_template']
        self.cols_and_filter = ['columns', 'filter']
        self.case_tile = ['case_tile_configuration']

        self.app = Application.new_app('domain', "Untitled Application")
        self.src_module = self.app.add_module(Module.new_module('Src Module', lang='en'))
        self.src_detail = getattr(self.src_module.case_details, "short")
        self.header_ = getattr(self.src_detail.columns[0], 'header')
        self.header_['en'] = 'status'
        self.filter_ = setattr(self.src_detail, 'filter', 'a > b')
        self.custom_variables = setattr(self.src_detail, 'custom_variables', 'def')
        self.custom_xml = setattr(self.src_detail, 'custom_xml', 'ghi')
        self.print_template = getattr(self.src_detail, 'print_template')
        self.print_template['name'] = 'test'
        self.case_tile_configuration = setattr(self.src_detail, 'persist_tile_on_forms', True)

    def test_overwrite_all(self):
        dest_module = self.app.add_module(Module.new_module('Dest Module', lang='en'))
        dest_detail = getattr(dest_module.case_details, "short")
        dest_detail.overwrite_attrs(self.src_detail, self.all_attrs)
        self.assertEqual(self.src_detail.to_json(), dest_detail.to_json())

    def test_overwrite_filter_column(self):
        dest_module = self.app.add_module(Module.new_module('Dest Module', lang='en'))
        dest_detail = getattr(dest_module.case_details, "short")
        dest_detail.overwrite_attrs(self.src_detail, self.cols_and_filter)

        self.assertEqual(self.src_detail.columns, dest_detail.columns)
        self.assertEqual(self.src_detail.filter, dest_detail.filter)
        self.remove_attrs(dest_detail)
        self.assertNotEqual(self.src_detail.to_json(), dest_detail.to_json())

    def test_overwrite_other_configs(self):
        dest_module = self.app.add_module(Module.new_module('Dest Module', lang='en'))
        dest_detail = getattr(dest_module.case_details, "short")
        dest_detail.overwrite_attrs(self.src_detail, self.case_tile)

        self.assertNotEqual(str(self.src_detail.columns), str(dest_detail.columns))
        self.assertNotEqual(self.src_detail.filter, dest_detail.filter)
        self.assertEqual(self.src_detail.persist_tile_on_forms, dest_detail.persist_tile_on_forms)

    def remove_attrs(self, dest_detail):
        delattr(self.src_detail, 'filter')
        delattr(self.src_detail, 'columns')
        delattr(dest_detail, 'filter')
        delattr(dest_detail, 'columns')
