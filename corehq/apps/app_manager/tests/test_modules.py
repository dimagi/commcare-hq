from django.test import SimpleTestCase

from unittest.mock import patch

from corehq.apps.app_manager.const import AUTO_SELECT_USERCASE, CASE_LIST_FILTER_LOCATIONS_FIXTURE
from corehq.apps.app_manager.models import (
    AdvancedModule,
    AdvancedOpenCaseAction,
    Application,
    Assertion,
    AutoSelectCase,
    CaseIndex,
    CaseSearch,
    CaseSearchLabel,
    CaseSearchProperty,
    ConditionalCaseUpdate,
    DefaultCaseSearchProperty,
    LoadUpdateAction,
    Module,
    ReportAppConfig,
    ReportModule,
)
from corehq.apps.app_manager.views.modules import (
    _get_fixture_columns_options,
    _update_search_properties,
)
from corehq.apps.app_manager.util import purge_report_from_mobile_ucr
from corehq.apps.fixtures.models import LookupTable, TypeField
from corehq.apps.userreports.models import ReportConfiguration
from corehq.util.test_utils import flag_enabled


class ModuleTests(SimpleTestCase):

    def setUp(self):
        self.app = Application.new_app('domain', "Untitled Application")
        self.module = self.app.add_module(Module.new_module('Untitled Module', None))
        self.module.case_type = 'another_case_type'
        self.form = self.module.new_form("Untitled Form", None)

    def test_update_search_properties(self):
        module = Module()
        module.search_config.properties = [
            CaseSearchProperty(name='name', label={'fr': 'Nom'}),
            CaseSearchProperty(name='age', label={'fr': 'Âge'}),
        ]

        # Update name, add dob, and remove age
        props = list(_update_search_properties(module, [
            {'name': 'name', 'label': 'Name'},
            {'name': 'dob', 'label': 'Date of birth'}
        ], "en"))

        self.assertEqual(props[0]['label'], {'en': 'Name', 'fr': 'Nom'})
        self.assertEqual(props[1]['label'], {'en': 'Date of birth'})

    def test_update_search_properties_blank_same_lang(self):
        module = Module()
        module.search_config.properties = [
            CaseSearchProperty(name='name', label={'fr': 'Nom'}),
        ]

        # Blanking out a translation removes it from dict
        props = list(_update_search_properties(module, [
            {'name': 'name', 'label': ''},
        ], "fr"))
        self.assertEqual(props[0]['label'], {})

    def test_update_search_properties_blank_other_lang(self):
        module = Module()
        module.search_config.properties = [
            CaseSearchProperty(name='name', label={'fr': 'Nom'}),
        ]

        # Blank translations don't get added to dict
        props = list(_update_search_properties(module, [
            {'name': 'name', 'label': ''},
        ], "en"))
        self.assertEqual(props[0]['label'], {'fr': 'Nom'})

    def test_update_search_properties_required(self):
        module = Module()
        module.search_config.properties = [
            CaseSearchProperty(name='name', label={'en': 'Name'},
                               required=Assertion(test="true()", text={"en": "answer me"})),
        ]
        props = list(_update_search_properties(module, [
            {'name': 'name', 'label': 'Name', 'required_test': 'true()', 'required_text': 'answer me please'},
        ], "en"))
        self.assertEqual(props[0]['required'], {
            "test": "true()",
            "text": {"en": "answer me please"},
        })

    def test_update_search_properties_validation(self):
        module = Module()
        module.search_config.properties = [
            CaseSearchProperty(name='name', label={'en': 'Name'},
                               validations=[Assertion(test="true()", text={"en": "go ahead"})]),
        ]
        props = list(_update_search_properties(module, [{
            'name': 'name', 'label': 'Name', 'validation_test': 'false()', 'validation_text': 'you shall not pass',
        }], "en"))
        self.assertEqual(props[0]['validations'], [{
            "test": "false()",
            "text": {"en": "you shall not pass"},
        }])

    def test_get_fixture_columns_options(self):
        table = LookupTable(
            domain="module-domain",
            tag="duck",
            fields=[TypeField(name="wing")]
        )
        with patch.object(LookupTable.objects, "by_domain", lambda domain: [table]):
            result = _get_fixture_columns_options("module-domain")
            self.assertDictEqual(
                result,
                {
                    CASE_LIST_FILTER_LOCATIONS_FIXTURE: ['@id', 'name', 'site_code'],
                    "duck": ["wing"]
                }
            )


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
                name_update=ConditionalCaseUpdate(question_path="/data/question1"),
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
                name_update=ConditionalCaseUpdate(question_path="/data/question1"),
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
                name_update=ConditionalCaseUpdate(question_path="/data/question1"),
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
                name_update=ConditionalCaseUpdate(question_path="/data/question1"),
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
                name_update=ConditionalCaseUpdate(question_path="/data/question1"),
                case_indices=[CaseIndex(tag="parent")]
            ),
            AdvancedOpenCaseAction(
                case_tag="grandchild",
                case_type="grandchild",
                name_update=ConditionalCaseUpdate(question_path="/data/children/question1"),
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
    @patch('corehq.motech.repeaters.models.AppStructureRepeater.objects.by_domain')
    def test_purge_report_from_mobile_ucr(self, repeater_patch, get_db):
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
                          'case_tile_configuration', 'multi_select', 'print_template']
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
        self.multi_select = getattr(self.src_detail, 'multi_select')
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


class OverwriteCaseSearchConfigTests(SimpleTestCase):
    def setUp(self):
        self.all_attrs = ['search_properties', 'search_default_properties', 'search_claim_options']

        self.app = Application.new_app('domain', "Untitled Application")
        self.src_module = self.app.add_module(Module.new_module('Src Module', lang='en'))
        self.case_search_config = CaseSearch(
            search_label=CaseSearchLabel(
                label={
                    'en': 'Search Patients Nationally'
                }
            ),
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
                CaseSearchProperty(name='dob', label={'en': 'Date of birth'})
            ],
            auto_launch=True,
            default_search=True,
            additional_relevant="instance('groups')/groups/group",
            search_filter="name = instance('item-list:trees')/trees_list/trees[favorite='yes']/name",
            search_button_display_condition="false()",
            blacklisted_owner_ids_expression="instance('commcaresession')/session/context/userid",
            default_properties=[
                DefaultCaseSearchProperty(
                    property='ɨŧsȺŧɍȺᵽ',
                    defaultValue=("instance('casedb')/case"
                                  "[@case_id='instance('commcaresession')/session/data/case_id']/ɨŧsȺŧɍȺᵽ")),
                DefaultCaseSearchProperty(
                    property='name',
                    defaultValue="instance('locations')/locations/location[@id=123]/@type"),
            ],
        )
        self.src_module.search_config = self.case_search_config
        self.dest_module = self.app.add_module(Module.new_module('Dest Module', lang='en'))

    def test_overwrite_all(self):
        self.dest_module.search_config.overwrite_attrs(self.src_module.search_config, self.all_attrs)
        self.assertEqual(self.src_module.search_config.to_json(), self.dest_module.search_config.to_json())

    def test_overwrite_properties(self):
        self.dest_module.search_config = CaseSearch()
        self.dest_module.search_config.overwrite_attrs(self.src_module.search_config, ["search_properties"])
        self.assertEqual(
            self.src_module.search_config.to_json()["properties"],
            self.dest_module.search_config.to_json()["properties"]
        )
        # ensure that the rest is the same as the default config
        dest_json = self.dest_module.search_config.to_json()
        dest_json.pop("properties", [])
        blank_json = CaseSearch().to_json()
        blank_json.pop("properties", [])
        self.assertEqual(dest_json, blank_json)

    def test_overwrite_default_properties(self):
        self.dest_module.search_config = CaseSearch()
        self.dest_module.search_config.overwrite_attrs(
            self.src_module.search_config,
            ["search_default_properties"]
        )
        self.assertEqual(
            self.src_module.search_config.to_json()["default_properties"],
            self.dest_module.search_config.to_json()["default_properties"]
        )
        # ensure that the rest is the same as the default config
        dest_json = self.dest_module.search_config.to_json()
        dest_json.pop("default_properties", [])
        blank_json = CaseSearch().to_json()
        blank_json.pop("default_properties", [])
        self.assertEqual(dest_json, blank_json)

    def test_overwrite_options(self):
        self.dest_module.search_config = CaseSearch(
            properties=[CaseSearchProperty(name='age', label={'en': 'Age'})],
            default_properties=[DefaultCaseSearchProperty(
                property='location', defaultValue="instance('locations')/locations/location[@id=123]/location_id"
            )]
        )
        original_json = self.dest_module.search_config.to_json()
        self.dest_module.search_config.overwrite_attrs(self.src_module.search_config, ["search_claim_options"])
        final_json = self.dest_module.search_config.to_json()

        # properties and default properties should be unchanged
        self.assertEqual(original_json["properties"], final_json["properties"])
        self.assertEqual(original_json["default_properties"], final_json["default_properties"])

        # everything else should match the source config
        src_json = self.src_module.search_config.to_json()
        for config_dict in (final_json, src_json):
            config_dict.pop("properties", [])
            config_dict.pop("default_properties", [])
        self.assertEqual(final_json, src_json)
