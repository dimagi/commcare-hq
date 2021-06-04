from django.test import SimpleTestCase

from mock import patch

from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    CaseSearch,
    CaseSearchAgainLabel,
    CaseSearchLabel,
    CaseSearchProperty,
    DefaultCaseSearchProperty,
    DetailColumn,
    Itemset,
    Module,
)
from corehq.apps.app_manager.suite_xml.sections.details import (
    AUTO_LAUNCH_EXPRESSION,
)
from corehq.apps.app_manager.suite_xml.sections.remote_requests import (
    RESULTS_INSTANCE,
)
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    TestXmlMixin,
    parse_normalize,
    patch_get_xform_resource_overrides,
)
from corehq.apps.builds.models import BuildSpec
from corehq.util.test_utils import flag_enabled

DOMAIN = 'test_domain'


@patch_get_xform_resource_overrides()
class RemoteRequestSuiteTest(SimpleTestCase, TestXmlMixin, SuiteMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        self.app = Application.new_app(DOMAIN, "Untitled Application")
        self.app._id = '123'
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
        self.module.case_details.short.columns.append(
            DetailColumn.wrap(dict(
                header={"en": "moon"},
                model="case",
                format="calculate",
                field="whatever",
                calc_xpath="instance('item-list:moons')/moons_list/moons[favorite='yes']/name",
            ))
        )
        self.module.case_details.short.columns.append(
            DetailColumn.wrap(dict(
                header={"en": "Parent's Whatever"},
                model="case",
                format="plain",
                field="parent/whatever",
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
            search_label=CaseSearchLabel(
                label={
                    'en': 'Search Patients Nationally'
                }
            ),
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
                CaseSearchProperty(name='dob', label={'en': 'Date of birth'})
            ],
            default_relevant=True,
            additional_relevant="instance('groups')/groups/group",
            search_filter="name = instance('item-list:trees')/trees_list/trees[favorite='yes']/name",
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

        # wrap to have assign_references called
        self.app = Application.wrap(self.app.to_json())
        # reset to newly wrapped module
        self.module = self.app.modules[0]

    def test_search_config_model(self, *args):
        config = CaseSearch()

        config.default_relevant = True
        self.assertEqual(config.get_relevant(), """
            count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/search_case_id]) = 0
        """.strip())

        config.default_relevant = False
        self.assertEqual(config.get_relevant(), "")

        config.additional_relevant = "double(now()) mod 2 = 0"
        self.assertEqual(config.get_relevant(), "double(now()) mod 2 = 0")

        config.default_relevant = True
        self.assertEqual(config.get_relevant(), "(count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/search_case_id]) = 0) and (double(now()) mod 2 = 0)")

    @flag_enabled("USH_CASE_CLAIM_UPDATES")
    def test_remote_request(self, *args):
        """
        Suite should include remote-request if searching is configured
        """
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.app.create_suite()
        self.assertXmlPartialEqual(
            self.get_xml('remote_request').decode('utf-8').format(module_id="m0"),
            suite,
            "./remote-request[1]"
        )

    @flag_enabled("USH_CASE_CLAIM_UPDATES")
    def test_remote_request_custom_detail(self, *args):
        """Remote requests for modules with custom details point to the custom detail
        """
        self.module.case_details.short.custom_xml = '<detail id="m0_case_short"></detail>'
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('remote_request_custom_detail'), suite, "./remote-request[1]")

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
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
        self.assertXmlPartialEqual(
            self.get_xml('remote_request').decode('utf-8').format(module_id="m0"),
            suite,
            "./remote-request[1]"
        )
        self.assertXmlPartialEqual(
            self.get_xml('remote_request').decode('utf-8').format(module_id="m1"),
            suite,
            "./remote-request[2]"
        )

    def test_case_search_action(self, *args):
        """
        Case search action should be added to case list and a new search detail should be created
        """
        # Regular and advanced modules should get the search detail
        search_config = CaseSearch(
            search_label=CaseSearchLabel(
                label={
                    'en': 'Advanced Search'
                }
            ),
            search_again_label=CaseSearchAgainLabel(
                label={
                    'en': 'Search One More Time'
                }
            ),
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

        # wrap to have assign_references called
        self.app = Application.wrap(self.app.to_json())

        suite = self.app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('search_command_detail'), suite, "./detail")

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
    def test_case_search_filter(self, *args):
        search_filter = "rating > 3"
        self.module.search_config.search_filter = search_filter
        suite = self.app.create_suite()
        suite = parse_normalize(suite, to_string=False)
        ref_path = './remote-request[1]/session/datum/@nodeset'
        self.assertEqual(
            "instance('{}')/{}/case[@case_type='{}'][{}]".format(
                RESULTS_INSTANCE,
                RESULTS_INSTANCE,
                self.module.case_type,
                search_filter
            ),
            suite.xpath(ref_path)[0]
        )

    def test_case_search_action_relevant_condition(self, *args):
        condition = "'foo' = 'bar'"
        self.module.search_config.search_button_display_condition = condition
        suite = self.app.create_suite()
        suite = parse_normalize(suite, to_string=False)
        self.assertEqual(condition, suite.xpath('./detail[1]/action/@relevant')[0])

    def test_case_search_auto_launch_off(self, *args):
        self.module.search_config.auto_launch = True
        suite = self.app.create_suite()
        expected = """
        <partial>
          <action auto_launch="false()" redo_last="false">
            <display>
              <text>
                <locale id="case_search.m0"/>
              </text>
            </display>
            <stack>
              <push>
                <mark/>
                <command value="'search_command.m0'"/>
              </push>
            </stack>
          </action>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./detail[1]/action")

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
    def test_case_search_auto_launch(self, *args):
        self.module.search_config.auto_launch = True
        suite = self.app.create_suite()
        expected = f"""
        <partial>
          <action auto_launch="{AUTO_LAUNCH_EXPRESSION}" redo_last="false">
            <display>
              <text>
                <locale id="case_search.m0"/>
              </text>
            </display>
            <stack>
              <push>
                <mark/>
                <command value="'search_command.m0'"/>
              </push>
            </stack>
          </action>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./detail[1]/action")

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

        # wrap to have assign_references called
        self.app = Application.wrap(self.app.to_json())

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

        # wrap to have assign_references called
        self.app = Application.wrap(self.app.to_json())

        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('search_config_blacklisted_owners'), suite, "./remote-request[1]")

    def test_prompt_hint(self, *args):
        self.module.search_config.properties[0].hint = {'en': 'Search against name'}
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt key="name">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
              <hint>
                  <text>
                    <locale id="search_property.m0.name.hint"/>
                  </text>
              </hint>
            </display>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")

    def test_default_search(self, *args):
        suite = self.app.create_suite()
        suite = parse_normalize(suite, to_string=False)
        self.assertEqual("false", suite.xpath("./remote-request[1]/session/query/@default_search")[0])

        self.module.search_config.default_search = True
        suite = self.app.create_suite()
        suite = parse_normalize(suite, to_string=False)
        self.assertEqual("true", suite.xpath("./remote-request[1]/session/query/@default_search")[0])

    def test_prompt_appearance(self, *args):
        """Setting the appearance to "barcode"
        """
        # Shouldn't be included for versions before 2.50
        self.module.search_config.properties[0].appearance = 'barcode_scan'
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt key="name">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")

        self.app.build_spec = BuildSpec(version='2.50.0', build_number=1)
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt key="name" appearance="barcode_scan">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")

    def test_prompt_daterange(self, *args):
        """Setting the appearance to "daterange"
        """
        # Shouldn't be included for versions before 2.50
        self.module.search_config.properties[0].input_ = 'daterange'
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt key="name" input="daterange">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")

        self.app.build_spec = BuildSpec(version='2.50.0', build_number=1)
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt key="name" input="daterange">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")

    def test_prompt_address(self, *args):
        """Setting the appearance to "address"
        """
        # Shouldn't be included for versions before 2.50
        self.module.search_config.properties[0].appearance = 'address'
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt key="name">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")

        self.app.build_spec = BuildSpec(version='2.50.0', build_number=1)
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt key="name" input="address">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")

    def test_prompt_address_receiver(self, *args):
        """Setting the appearance to "address"
        """
        # Shouldn't be included for versions before 2.50
        self.module.search_config.properties[0].receiver_expression = 'home-street'
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt key="name" receive="home-street">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")

    def test_prompt_hidden(self, *args):
        """Setting the appearance to "address"
        """
        # Shouldn't be included for versions before 2.50
        self.module.search_config.properties[0].hidden = True
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt key="name" hidden="true">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")

    def test_prompt_address_receiver_itemset(self, *args):
        """Setting the appearance to "address"
        """
        # Shouldn't be included for versions before 2.50
        self.module.search_config.properties[0].receiver_expression = 'home-street'
        self.module.search_config.properties[0].input_ = 'select1'
        self.module.search_config.properties[0].itemset = Itemset(
            instance_id='states',
            instance_uri="jr://fixture/item-list:states",
            nodeset="instance('states')/state_list/state[@state_name = 'Uttar Pradesh']",
            label='name',
            value='id',
            sort='id',
        )
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt key="name" input="select1" receive="home-street">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
            <itemset nodeset="instance('states')/state_list/state[@state_name = 'Uttar Pradesh']">
              <label ref="name"/>
              <value ref="id"/>
              <sort ref="id"/>
            </itemset>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")

    def test_prompt_itemset(self):
        self.module.search_config.properties[0].input_ = 'select1'
        self.module.search_config.properties[0].itemset = Itemset(
            instance_id='states',
            instance_uri="jr://fixture/item-list:states",
            nodeset="instance('states')/state_list/state[@state_name = 'Uttar Pradesh']",
            label='name',
            value='id',
            sort='id',
        )
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt key="name" input="select1">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
            <itemset nodeset="instance('states')/state_list/state[@state_name = 'Uttar Pradesh']">
              <label ref="name"/>
              <value ref="id"/>
              <sort ref="id"/>
            </itemset>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")

        expected_instance = """
        <partial>
          <instance id="states" src="jr://fixture/item-list:states"/>
        </partial>
        """
        self.assertXmlPartialEqual(
            expected_instance,
            suite,
            "./remote-request[1]/instance[@id='states']",
        )

    @flag_enabled("USH_CASE_CLAIM_UPDATES")
    def test_prompt_default_value(self, *args):
        """Setting the default to "default_value"
        """
        # Shouldn't be included for versions before 2.51
        self.module.search_config.properties[0].default_value = 'foo'
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt key="name">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")
        self.app.build_spec = BuildSpec(version='2.51.0', build_number=1)
        self.module.search_config.properties[0].default_value = 'foo'
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt default="foo" key="name">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")

        self.app.build_spec = BuildSpec(version='2.51.0', build_number=1)
        self.module.search_config.properties[0].default_value = "3"
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt default="3" key="name">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")
