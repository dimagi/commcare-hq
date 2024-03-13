from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase

from corehq.apps.app_manager.const import REGISTRY_WORKFLOW_SMART_LINK
from corehq.apps.app_manager.exceptions import UnknownInstanceError
from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    Assertion,
    CaseSearch,
    CaseSearchAgainLabel,
    CaseSearchCustomSortProperty,
    CaseSearchLabel,
    CaseSearchProperty,
    DefaultCaseSearchProperty,
    DetailColumn,
    Itemset,
    Module,
    ShadowModule,
)
from corehq.apps.app_manager.suite_xml.generator import SuiteGenerator
from corehq.apps.app_manager.suite_xml.post_process.remote_requests import (
    RESULTS_INSTANCE,
    RemoteRequestFactory,
)
from corehq.apps.app_manager.suite_xml.sections.details import (
    AUTO_LAUNCH_EXPRESSIONS,
    DetailContributor,
)
from corehq.apps.app_manager.suite_xml.sections.entries import (
    EntriesContributor,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    parse_normalize,
    patch_get_xform_resource_overrides,
)
from corehq.apps.builds.models import BuildSpec
from corehq.apps.case_search.const import EXCLUDE_RELATED_CASES_FILTER
from corehq.util.test_utils import flag_enabled

DOMAIN = 'test_domain'


@patch('corehq.util.view_utils.get_url_base', new=lambda: "https://www.example.com")
@patch_get_xform_resource_overrides()
@patch.object(Application, 'supports_data_registry', lambda: True)
class RemoteRequestSmartLinkTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        self.factory = AppFactory(domain=DOMAIN, build_version='2.53.0')
        self.app_id = uuid4().hex
        self.factory.app._id = self.app_id
        module, form = self.factory.new_basic_module('basic', 'tree')
        self.factory.form_requires_case(form, 'tree')
        child_module, child_form = self.factory.new_basic_module('child', 'leaf', parent_module=module)
        self.factory.form_requires_case(child_form, 'leaf')

        child_module.search_config = CaseSearch(
            search_label=CaseSearchLabel(label={'en': 'Search'}),
            properties=[CaseSearchProperty(name=field) for field in ['name', 'shape']],
            data_registry="a_registry",
            data_registry_workflow=REGISTRY_WORKFLOW_SMART_LINK,
        )
        child_module.assign_references()

        child_module.session_endpoint_id = "child_endpoint"
        child_module.parent_select.active = True
        child_module.parent_select.module_id = module.unique_id

        generator = SuiteGenerator(self.factory.app)
        detail_section_elements = generator.add_section(DetailContributor)
        entries = EntriesContributor(generator.suite, self.factory.app, self.factory.app.modules)
        generator.suite.entries.extend(entries.get_module_contributions(child_module))
        self.request_factory = RemoteRequestFactory(generator.suite, child_module, detail_section_elements)

    def testSmartLinkFunction(self):
        concat_params = [
            "'https://www.example.com/a/'",
            "$domain",
            f"'/app/v1/{self.app_id}/child_endpoint/'",
            "'?case_id_leaf='",
            "$case_id_leaf",
            "'&case_id='",
            "$case_id",
        ]
        self.assertEqual(
            self.request_factory.get_smart_link_function(),
            f'concat({", ".join(concat_params)})'
        )

    def testSmartLinkVariables(self):
        vars = self.request_factory.get_smart_link_variables()
        self.assertEqual([v.name for v in vars], ['domain', 'case_id', 'case_id_leaf'])
        session_case_id = "instance('commcaresession')/session/data/search_case_id"
        self.assertEqual([v.xpath.function for v in vars], [
            f"instance('results')/results/case[@case_id={session_case_id}]/commcare_project",
            "instance('commcaresession')/session/data/case_id",
            "instance('commcaresession')/session/data/search_case_id",
        ])

    def testSuite(self):
        suite = self.factory.app.create_suite()
        self.assertXmlPartialEqual(
            self.get_xml('smart_link_remote_request').decode('utf-8').format(app_id=self.app_id),
            suite,
            "./remote-request[1]"
        )


@patch('corehq.util.view_utils.get_url_base', new=lambda: "https://www.example.com")
@patch_get_xform_resource_overrides()
class RemoteRequestSuiteTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        self.app = Application.new_app(DOMAIN, "Untitled Application")
        self.app._id = '123'
        self.app.build_spec = BuildSpec(version='2.53.0', build_number=1)
        self.module = self.app.add_module(Module.new_module("Untitled Module", None))
        self.form = self.app.new_form(0, "Untitled Form", None)
        self.form.requires = 'case'
        self.module.case_type = 'case'

        # chosen xpath just used to reference more instances - not considered valid to use in apps
        self.module.case_details.short.columns.append(
            DetailColumn.wrap(dict(
                header={"en": "report_name"},
                model="case",
                format="plain",
                field="instance('reports')/report[1]/name",
                useXpathExpression=True,
            ))
        )
        self.module.case_details.short.columns.append(
            DetailColumn.wrap(dict(
                header={"en": "moon"},
                model="case",
                format="plain",
                field="instance('item-list:moons')/moons_list/moons[favorite='yes']/name",
                useXpathExpression=True,
            ))
        )
        self.module.case_details.short.columns.append(
            DetailColumn.wrap(dict(
                header={"en": "Parent's Whatever"},
                model="case",
                format="plain",
                field="parent/whatever",
                useXpathExpression=False,
            ))
        )
        self.module.case_details.long.columns.append(
            DetailColumn.wrap(dict(
                header={"en": "ledger_name"},
                model="case",
                format="plain",
                field="instance('ledgerdb')/ledgers/name/name",
                useXpathExpression=True,
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
                CaseSearchProperty(name='dob', label={'en': 'Date of birth'}, input_="date"),
                CaseSearchProperty(name='consent', label={'en': 'Consent to search'}, input_="checkbox"),
            ],
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

    def test_search_config_relevant(self):
        config = CaseSearch()

        self.assertEqual(
            config.get_relevant(config.case_session_var),
            "count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/search_case_id]) = 0")  # noqa: E501

        config.additional_relevant = "double(now()) mod 2 = 0"
        self.assertEqual(
            config.get_relevant(config.case_session_var),
            "(count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/search_case_id]) = 0) and (double(now()) mod 2 = 0)")  # noqa: E501

    def test_search_config_relevant_multi_select(self):
        config = CaseSearch()

        self.assertEqual(config.get_relevant(config.case_session_var, multi_select=True), "$case_id != ''")

        config.additional_relevant = "double(now()) mod 2 = 0"
        self.assertEqual(config.get_relevant(config.case_session_var, multi_select=True),
                         "($case_id != '') and (double(now()) mod 2 = 0)")

    @flag_enabled("USH_CASE_CLAIM_UPDATES")
    @flag_enabled('USH_SEARCH_FILTER')
    def test_remote_request(self):
        """
        Suite should include remote-request if searching is configured
        """
        suite = self.app.create_suite()
        self.assertXmlPartialEqual(
            self.get_xml('remote_request').decode('utf-8').format(module_id="m0"),
            suite,
            "./remote-request[1]"
        )

    @flag_enabled("USH_CASE_CLAIM_UPDATES")
    @flag_enabled('USH_SEARCH_FILTER')
    def test_remote_request_custom_detail(self):
        """Remote requests for modules with custom details point to the custom detail
        """
        self.module.case_details.short.custom_xml = '<detail id="m0_case_short"></detail>'
        suite = self.app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('remote_request_custom_detail'), suite, "./remote-request[1]")

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
    @flag_enabled('USH_SEARCH_FILTER')
    @patch('corehq.apps.app_manager.suite_xml.post_process.resources.ResourceOverrideHelper.update_suite',
           lambda _: None)
    def test_duplicate_remote_request(self):
        """
        Adding a second search config should not affect the initial one.
        """
        copy_app = Application.wrap(self.app.to_json())
        copy_app.modules.append(Module.wrap(copy_app.modules[0].to_json()))
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

    def test_case_search_action(self):
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
    @flag_enabled('USH_SEARCH_FILTER')
    def test_case_search_filter(self):
        search_filter = "rating > 3"
        self.module.search_config.search_filter = search_filter
        suite = self.app.create_suite()
        suite = parse_normalize(suite, to_string=False)
        ref_path = './remote-request[1]/session/datum/@nodeset'
        self.assertEqual(
            "instance('{}')/{}/case[@case_type='{}'][{}]{}".format(
                RESULTS_INSTANCE,
                RESULTS_INSTANCE,
                self.module.case_type,
                search_filter,
                EXCLUDE_RELATED_CASES_FILTER
            ),
            suite.xpath(ref_path)[0]
        )

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
    @flag_enabled('USH_SEARCH_FILTER')
    def test_additional_types(self):
        another_case_type = "another_case_type"
        self.module.search_config.additional_case_types = [another_case_type]
        suite_xml = self.app.create_suite()
        suite = parse_normalize(suite_xml, to_string=False)
        ref_path = './remote-request[1]/session/datum/@nodeset'
        self.assertEqual(
            "instance('{}')/{}/case[@case_type='{}' or @case_type='{}'][{}]{}".format(
                RESULTS_INSTANCE,
                RESULTS_INSTANCE,
                self.module.case_type,
                another_case_type,
                self.module.search_config.search_filter,
                EXCLUDE_RELATED_CASES_FILTER
            ),
            suite.xpath(ref_path)[0]
        )
        self.assertXmlPartialEqual(
            """
            <partial>
              <data key="case_type" ref="'case'"/>
              <data key="case_type" ref="'another_case_type'"/>
            </partial>
            """,
            suite_xml,
            "./remote-request[1]/session/query/data[@key='case_type']"
        )

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
    def test_additional_types__shadow_module(self):
        shadow_module = self.app.add_module(ShadowModule.new_module("shadow", "en"))
        shadow_module.source_module_id = self.module.get_or_create_unique_id()
        shadow_module.search_config = CaseSearch(
            search_label=CaseSearchLabel(
                label={
                    'en': 'Search from Shadow Module'
                }
            ),
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
            ],
        )
        another_case_type = "another_case_type"
        self.module.search_config.additional_case_types = [another_case_type]
        app = Application.wrap(self.app.to_json())
        suite_xml = app.create_suite()
        suite = parse_normalize(suite_xml, to_string=False)
        ref_path = './remote-request[2]/session/datum/@nodeset'
        self.assertEqual(
            "instance('{}')/{}/case[@case_type='{}' or @case_type='{}']{}".format(
                RESULTS_INSTANCE,
                RESULTS_INSTANCE,
                self.module.case_type,
                another_case_type,
                EXCLUDE_RELATED_CASES_FILTER
            ),
            suite.xpath(ref_path)[0]
        )
        self.assertXmlPartialEqual(
            """
            <partial>
              <data key="case_type" ref="'case'"/>
              <data key="case_type" ref="'another_case_type'"/>
            </partial>
            """,
            suite_xml,
            "./remote-request[2]/session/query/data[@key='case_type']"
        )

    def test_case_search_action_relevant_condition(self):
        condition = "'foo' = 'bar'"
        self.module.search_config.search_button_display_condition = condition
        suite = self.app.create_suite()
        suite = parse_normalize(suite, to_string=False)
        self.assertEqual(condition, suite.xpath('./detail[1]/action/@relevant')[0])

    def test_case_search_auto_launch_off(self):
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
    def test_case_search_auto_launch(self):
        self.module.search_config.auto_launch = True
        suite = self.app.create_suite()
        expected = f"""
        <partial>
          <action auto_launch="{AUTO_LAUNCH_EXPRESSIONS['single-select']}" redo_last="false">
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

    def test_only_default_properties(self):
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
        suite = self.app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('search_config_default_only'), suite, "./remote-request[1]")

    def test_custom_related_case_property(self):
        self.module.search_config.custom_related_case_property = "potential_duplicate_id"
        suite = self.app.create_suite()

        expected = """
        <partial>
          <data key="x_commcare_custom_related_case_property" ref="'potential_duplicate_id'"/>
        </partial>
        """
        xpath = "./remote-request[1]/session/query/data[@key='x_commcare_custom_related_case_property']"
        self.assertXmlPartialEqual(expected, suite, xpath)

    def test_blacklisted_owner_ids(self):
        self.module.search_config = CaseSearch(
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
            ],
            blacklisted_owner_ids_expression="instance('commcaresession')/session/context/userid",
        )

        # wrap to have assign_references called
        self.app = Application.wrap(self.app.to_json())
        suite = self.app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('search_config_blacklisted_owners'), suite, "./remote-request[1]")

    def test_custom_sort_properties(self):
        self.module.search_config = CaseSearch(
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
            ],
            custom_sort_properties=[
                CaseSearchCustomSortProperty(
                    property_name='name'
                ), CaseSearchCustomSortProperty(
                    property_name='date_of_birth',
                    sort_type='date',
                    direction='descending'
                )
            ],
        )
        expected = """
        <partial>
          <data key="commcare_sort" ref="'+name:exact,-date_of_birth:date'"/>
        </partial>
        """

        # wrap to have assign_references called
        self.app = Application.wrap(self.app.to_json())
        suite = self.app.create_suite()
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/data[@key='commcare_sort']")

    def test_prompt_hint(self):
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

    def test_default_search(self):
        suite = self.app.create_suite()
        suite = parse_normalize(suite, to_string=False)
        self.assertEqual("false", suite.xpath("./remote-request[1]/session/query/@default_search")[0])

        self.module.search_config.default_search = True
        suite = self.app.create_suite()
        suite = parse_normalize(suite, to_string=False)
        self.assertEqual("true", suite.xpath("./remote-request[1]/session/query/@default_search")[0])

    def test_prompt_appearance(self):
        """Setting the appearance to "barcode"
        """
        self.module.search_config.properties[0].appearance = 'barcode_scan'
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

        # Shouldn't be included for versions before 2.50
        self.app.build_spec = BuildSpec(version='2.35.0', build_number=1)
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

    def test_prompt_daterange(self):
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

    def test_prompt_address(self):
        """Setting the appearance to "address"
        """
        self.module.search_config.properties[0].appearance = 'address'
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
        # Shouldn't be included for versions before 2.50
        self.app.build_spec = BuildSpec(version='2.35.0', build_number=1)
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

    def test_prompt_address_receiver(self):
        """Setting the appearance to "address"
        """
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

    def test_prompt_hidden(self):
        """Setting the appearance to "address"
        """
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

    def test_prompt_address_receiver_itemset(self):
        """Setting the appearance to "address"
        """
        self.module.search_config.properties[0].receiver_expression = 'home-street'
        self.module.search_config.properties[0].input_ = 'select1'
        self.module.search_config.properties[0].itemset = Itemset(
            instance_id='states',
            nodeset="instance('item-list:states')/state_list/state[@state_name = 'Uttar Pradesh']",
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
            <itemset nodeset="instance('item-list:states')/state_list/state[@state_name = 'Uttar Pradesh']">
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
            nodeset="instance('item-list:states')/state_list/state[@state_name = 'Uttar Pradesh']",
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
            <itemset nodeset="instance('item-list:states')/state_list/state[@state_name = 'Uttar Pradesh']">
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
          <instance id="item-list:states" src="jr://fixture/item-list:states"/>
        </partial>
        """
        self.assertXmlPartialEqual(
            expected_instance,
            suite,
            "./remote-request[1]/instance[@id='item-list:states']",
        )

    def test_prompt_itemset_unrecognized_instance(self):
        instance_id = 'abcdef'
        self.module.search_config.properties[0].input_ = 'select1'
        self.module.search_config.properties[0].itemset = Itemset(
            instance_id=instance_id,
            # The instance ID here should be prefixed with
            # commcare-reports: or item-list:
            nodeset=f"instance('{instance_id}')/rows/row",
            label='name',
            value='id',
            sort='id',
        )
        with self.assertRaises(UnknownInstanceError):
            self.app.create_suite()

    @flag_enabled('MOBILE_UCR')
    def test_prompt_itemset_mobile_report(self):
        instance_id = 'commcare-reports:abcdef'
        self.module.search_config.properties[0].input_ = 'select1'
        self.module.search_config.properties[0].itemset = Itemset(
            instance_id=instance_id,
            nodeset=f"instance('{instance_id}')/rows/row",
            label='name',
            value='id',
            sort='id',
        )
        suite = self.app.create_suite()
        expected = f"""
        <partial>
          <prompt key="name" input="select1">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
            <itemset nodeset="instance('{instance_id}')/rows/row">
              <label ref="name"/>
              <value ref="id"/>
              <sort ref="id"/>
            </itemset>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")

        expected_instance = f"""
        <partial>
          <instance id="{instance_id}" src="jr://fixture/commcare-reports:abcdef"/>
        </partial>
        """
        self.assertXmlPartialEqual(
            expected_instance,
            suite,
            f"./remote-request[1]/instance[@id='{instance_id}']",
        )

    @flag_enabled("USH_CASE_CLAIM_UPDATES")
    def test_prompt_default_value(self):
        """Setting the default to "default_value"
        """
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

        # Shouldn't be included for versions before 2.51
        self.app.build_spec = BuildSpec(version='2.35.0', build_number=1)
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

    def test_allow_blank_value(self):
        self.module.search_config.properties[0].allow_blank_value = True
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt key="name" allow_blank_value="true">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")

    def test_exclude_from_search(self):
        self.module.search_config.properties[0].exclude = True
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt key="name" exclude="true()">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")

    def test_case_search_title_translation(self):
        self.app.build_spec = BuildSpec(version='2.53.0', build_number=1)
        suite = self.app.create_suite()
        expected_query_title = """
        <partial>
            <title>
              <text>
                <locale id="case_search.m0.inputs"/>
              </text>
            </title>
        </partial>
        """
        expected_search_detail = """
        <partial>
            <title>
              <text>
                <locale id="cchq.case"/>
              </text>
            </title>
        </partial>
        """
        expected_case_detail = """
        <partial>
            <title>
              <text>
                <locale id="cchq.case"/>
              </text>
            </title>
        </partial>
        """
        self.assertXmlPartialEqual(expected_query_title, suite, "./remote-request[1]/session/query/title")
        self.assertXmlPartialEqual(expected_search_detail, suite, "./detail[@id='m0_search_short']/title")
        self.assertXmlPartialEqual(expected_case_detail, suite, "./detail[@id='m0_case_short']/title")

    def test_required(self):
        self.module.search_config.properties[0].required = Assertion(
            test="#session/user/data/is_supervisor = 'n'",
        )
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt key="name">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
            <required test="instance('commcaresession')/session/user/data/is_supervisor = 'n'">
              <text>
                <locale id="search_property.m0.name.required.text"/>
              </text>
            </required>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt[@key='name']")

    def test_case_search_validation_conditions(self):
        self.module.search_config.properties = [
            CaseSearchProperty(name='name', label={'en': 'Name'}, validations=[
                Assertion(test='2 + 2 = 5', text={"en": ""})
            ]),
            CaseSearchProperty(name='email', label={'en': 'Email'}, validations=[
                Assertion(
                    test="contains(instance('search-input:results')/input/field[@name='email'], '@')",
                    text={"en": "Please enter a valid email address",
                          "it": "Si prega di inserire un indirizzo email valido"},
                )
            ]),
        ]
        suite = self.app.create_suite()
        expected = """
        <partial>
          <prompt key="name">
            <display>
              <text>
                <locale id="search_property.m0.name"/>
              </text>
            </display>
            <validation test="2 + 2 = 5" />
          </prompt>
          <prompt key="email">
            <display>
              <text>
                <locale id="search_property.m0.email"/>
              </text>
            </display>
            <validation test="contains(instance('search-input:results')/input/field[@name='email'], '@')">
              <text>
                <locale id="search_property.m0.email.validation.0.text"/>
              </text>
            </validation>
          </prompt>
        </partial>
        """
        self.assertXmlPartialEqual(expected, suite, "./remote-request[1]/session/query/prompt")

    def test_group(self):
        self.module.search_config.properties = [
            CaseSearchProperty(is_group=True, group_key='group_header_0', label={'en': 'Personal Information'}),
            CaseSearchProperty(name='name', group_key='group_header_0', label={'en': 'Name'}),
            CaseSearchProperty(name='dob', group_key='group_header_0',
                               label={'en': 'Date of birth'}, input_="date"),
            CaseSearchProperty(is_group=True, group_key='group_header_3', label={'en': 'Authorization'}),
            CaseSearchProperty(name='consent', group_key='group_header_3',
                               label={'en': 'Consent to search'}, input_="checkbox"),
        ]
        suite = self.app.create_suite()
        expected = """
          <partial>
            <group key="group_header_0">
              <display>
                <text>
                  <locale id="search_property.m0.group_header_0"/>
                </text>
              </display>
            </group>
            <group key="group_header_3">
              <display>
                <text>
                  <locale id="search_property.m0.group_header_3"/>
                </text>
              </display>
            </group>
          </partial>
        """
        self.assertXmlPartialEqual(expected, suite,
                                  "./remote-request[1]/session/query/group")

        expected = """
          <partial>
            <prompt key="name" group_key="group_header_0">
              <display>
                <text>
                  <locale id="search_property.m0.name"/>
                </text>
              </display>
            </prompt>
            <prompt group_key="group_header_0" input="date" key="dob">
              <display>
                <text>
                  <locale id="search_property.m0.dob"/>
                </text>
              </display>
            </prompt>
            <prompt group_key="group_header_3" input="checkbox" key="consent">
              <display>
                <text>
                  <locale id="search_property.m0.consent"/>
                </text>
              </display>
            </prompt>
          </partial>
        """
        self.assertXmlPartialEqual(expected, suite,
                                  "./remote-request[1]/session/query/prompt")
