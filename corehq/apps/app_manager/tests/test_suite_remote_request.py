from django.test import SimpleTestCase

from mock import patch

from corehq.apps.app_manager.const import CLAIM_DEFAULT_RELEVANT_CONDITION
from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    CaseSearch,
    CaseSearchProperty,
    DefaultCaseSearchProperty,
    DetailColumn,
    Module,
)
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    TestXmlMixin,
    parse_normalize,
    patch_get_xform_resource_overrides,
)
from corehq.apps.builds.models import BuildSpec

DOMAIN = 'test_domain'


@patch_get_xform_resource_overrides()
class RemoteRequestSuiteTest(SimpleTestCase, TestXmlMixin, SuiteMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        self.app = Application.new_app(DOMAIN, "Untitled Application")
        self.app.build_spec = BuildSpec(version='2.35.0', build_number=1)
        self.module = self.app.add_module(Module.new_module("Untitled Module", None))
        self.app.new_form(0, "Untitled Form", None)
        self.module.case_type = 'case'
        # chosen xpath just used to reference more instances - not considered valid to use in apps
        self.module.case_details.short.columns.append(
            DetailColumn.wrap(dict(
                header={"en": "report_name"},
                model="case",
                format="calculate",
                field="whatever",
                calc_xpath="instance('reports')/report[1]/name",
            ))
        )
        self.module.case_details.long.columns.append(
            DetailColumn.wrap(dict(
                header={"en": "ledger_name"},
                model="case",
                format="calculate",
                field="whatever",
                calc_xpath="instance('ledgerdb')/ledgers/name/name",
            ))
        )
        self.module.search_config = CaseSearch(
            command_label={'en': 'Search Patients Nationally'},
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
                CaseSearchProperty(name='dob', label={'en': 'Date of birth'})
            ],
            relevant="{} and {}".format("instance('groups')/groups/group", CLAIM_DEFAULT_RELEVANT_CONDITION),
            default_properties=[
                DefaultCaseSearchProperty(
                    property='ɨŧsȺŧɍȺᵽ',
                    defaultValue=(
                        "instance('casedb')/case"
                        "[@case_id='instance('commcaresession')/session/data/case_id']"
                        "/ɨŧsȺŧɍȺᵽ")
                ),
                DefaultCaseSearchProperty(
                    property='name',
                    defaultValue="instance('locations')/locations/location[@id=123]/@type",
                ),
            ],
        )

    def test_remote_request(self, *args):
        """
        Suite should include remote-request if searching is configured
        """
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('remote_request'), suite, "./remote-request[1]")

    def test_remote_request_custom_detail(self, *args):
        """Remote requests for modules with custom details point to the custom detail
        """
        self.module.case_details.short.custom_xml = '<detail id="m0_case_short"></detail>'
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('remote_request_custom_detail'), suite, "./remote-request[1]")

    @patch('corehq.apps.app_manager.suite_xml.post_process.resources.ResourceOverrideHelper.update_suite')
    def test_duplicate_remote_request(self, *args):
        """
        Adding a second search config should not affect the initial one.
        """
        copy_app = Application.wrap(self.app.to_json())
        copy_app.modules.append(Module.wrap(copy_app.modules[0].to_json()))
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = copy_app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('remote_request'), suite, "./remote-request[1]")

    def test_case_search_action(self, *args):
        """
        Case search action should be added to case list and a new search detail should be created
        """
        # Regular and advanced modules should get the search detail
        search_config = CaseSearch(
            command_label={'en': 'Advanced Search'},
            properties=[CaseSearchProperty(name='name', label={'en': 'Name'})]
        )
        advanced_module = self.app.add_module(AdvancedModule.new_module("advanced", None))
        advanced_module.search_config = search_config

        # Modules with custom xml should not get the search detail
        module_custom = self.app.add_module(Module.new_module("custom_xml", None))
        module_custom.search_config = search_config
        module_custom.case_details.short.custom_xml = "<detail id='m2_case_short'></detail>"
        advanced_module_custom = self.app.add_module(AdvancedModule.new_module("advanced with custom_xml", None))
        advanced_module_custom.search_config = search_config
        advanced_module_custom.case_details.short.custom_xml = "<detail id='m3_case_short'></detail>"

        suite = self.app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('search_command_detail'), suite, "./detail")

    def test_case_search_action_relevant_condition(self, *args):
        condition = "'foo' = 'bar'"
        self.module.search_config.search_button_display_condition = condition
        suite = self.app.create_suite()
        suite = parse_normalize(suite, to_string=False)
        self.assertEqual(condition, suite.xpath('./detail[1]/action/@relevant')[0])

    def test_only_default_properties(self, *args):
        self.module.search_config = CaseSearch(
            default_properties=[
                DefaultCaseSearchProperty(
                    property='ɨŧsȺŧɍȺᵽ',
                    defaultValue=(
                        "instance('casedb')/case"
                        "[@case_id='instance('commcaresession')/session/data/case_id']"
                        "/ɨŧsȺŧɍȺᵽ")
                ),
                DefaultCaseSearchProperty(
                    property='name',
                    defaultValue="instance('locations')/locations/location[@id=123]/@type",
                ),
            ],
        )
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('search_config_default_only'), suite, "./remote-request[1]")

    def test_blacklisted_owner_ids(self, *args):
        self.module.search_config = CaseSearch(
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
            ],
            blacklisted_owner_ids_expression="instance('commcaresession')/session/context/userid",
        )
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('search_config_blacklisted_owners'), suite, "./remote-request[1]")
