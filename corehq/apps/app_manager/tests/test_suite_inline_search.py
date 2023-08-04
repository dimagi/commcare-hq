from django.test import SimpleTestCase

from corehq.apps.app_manager.const import WORKFLOW_FORM, WORKFLOW_PREVIOUS
from corehq.apps.app_manager.models import (
    Application,
    CaseSearch,
    CaseSearchProperty,
    ConditionalCaseUpdate,
    DetailColumn,
    DetailTab,
    FormLink,
    Itemset,
    Module,
    OpenCaseAction,
    ParentSelect,
    ShadowModule,
)
from corehq.apps.app_manager.suite_xml.post_process.remote_requests import (
    RESULTS_INSTANCE_INLINE,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    get_simple_form,
    patch_get_xform_resource_overrides,
)
from corehq.apps.builds.models import BuildSpec
from corehq.apps.case_search.const import EXCLUDE_RELATED_CASES_FILTER
from corehq.tests.util.xml import parse_normalize
from corehq.util.test_utils import flag_enabled

DOMAIN = 'test_domain'


@patch_get_xform_resource_overrides()
class InlineSearchSuiteTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite_inline_search')

    def setUp(self):
        self.app = Application.new_app(DOMAIN, "Untitled Application")
        self.app._id = '123'
        self.app.build_spec = BuildSpec(version='2.53.0', build_number=1)
        self.module = self.app.add_module(Module.new_module("Followup", None))
        self.form = self.app.new_form(0, "Untitled Form", None, attachment=get_simple_form("xmlns1.0"))
        self.form.requires = 'case'
        self.module.case_type = 'case'

        self.module.case_details.long.columns.append(
            DetailColumn.wrap(dict(
                header={"en": "name"},
                model="case",
                format="plain",
                field="whatever",
            ))
        )

        self.module.search_config = CaseSearch(
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
            ],
            search_filter="active = 'yes'",
            auto_launch=True,
            inline_search=True,
        )

        self.reg_module = self.app.add_module(Module.new_module("Registration", None))
        self.reg_form = self.app.new_form(1, "Untitled Form", None, attachment=get_simple_form("xmlns1.0"))
        self.reg_module.case_type = 'case'
        self.reg_form.actions.open_case = OpenCaseAction(
            name_update=ConditionalCaseUpdate(question_path="/data/question1")
        )
        self.reg_form.actions.open_case.condition.type = 'always'
        self.reg_form.post_form_workflow = WORKFLOW_FORM
        self.reg_form.form_links = [
            FormLink(form_id=self.form.get_unique_id(), form_module_id=self.module.unique_id)
        ]

        self.module.assign_references()
        self.reg_module.assign_references()
        # reset to newly wrapped module
        self.module = self.app.modules[0]
        self.form = self.module.forms[0]

    @flag_enabled('USH_SEARCH_FILTER')
    def test_inline_search(self):
        suite = self.app.create_suite()

        expected_entry_query = f"""
        <partial>
          <entry>
            <form>xmlns1.0</form>
            <post url="http://localhost:8000/a/test_domain/phone/claim-case/"
                relevant="count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]) = 0">
             <data key="case_id" ref="instance('commcaresession')/session/data/case_id"/>
            </post>
            <command id="m0-f0">
              <text>
                <locale id="forms.m0f0"/>
              </text>
            </command>
            <instance id="casedb" src="jr://instance/casedb"/>
            <instance id="commcaresession" src="jr://instance/session"/>
            <instance id="results:inline" src="jr://instance/remote/results:inline"/>
            <session>
                <query url="http://localhost:8000/a/test_domain/phone/search/123/"
                    storage-instance="{RESULTS_INSTANCE_INLINE}" template="case" default_search="false">
                  <title>
                    <text>
                      <locale id="case_search.m0.inputs"/>
                    </text>
                  </title>
                  <data key="case_type" ref="'case'"/>
                  <prompt key="name">
                    <display>
                      <text>
                        <locale id="search_property.m0.name"/>
                      </text>
                    </display>
                  </prompt>
                </query>
                <datum id="case_id" nodeset="instance('{RESULTS_INSTANCE_INLINE}')/results/case[@case_type='case'][@status='open'][active = 'yes'][not(commcare_is_related_case=true())]"
                    value="./@case_id" detail-select="m0_case_short" detail-confirm="m0_case_long"/>
            </session>
          </entry>
        </partial>"""  # noqa: E501
        self.assertXmlPartialEqual(expected_entry_query, suite, "./entry[1]")

        self.assertXmlDoesNotHaveXpath(suite, "./detail[@id='m0_case_short']/action")
        self.assertXmlDoesNotHaveXpath(suite, "./remote-request")
        self.assertXmlDoesNotHaveXpath(suite, "./detail[@id='m0_search_short']")
        self.assertXmlDoesNotHaveXpath(suite, "./detail[@id='m0_search_long']")

    @flag_enabled('USH_SEARCH_FILTER')
    def test_inline_search_case_list_item(self):
        self.module.case_list.show = True
        suite = self.app.create_suite()

        expected_entry_query = f"""
        <partial>
          <entry>
            <command id="m0-case-list">
              <text>
                <locale id="case_lists.m0"/>
              </text>
            </command>
            <instance id="results:inline" src="jr://instance/remote/results:inline"/>
            <session>
                <query url="http://localhost:8000/a/test_domain/phone/search/123/"
                    storage-instance="{RESULTS_INSTANCE_INLINE}" template="case" default_search="false">
                  <title>
                    <text>
                        <locale id="case_search.m0.inputs"/>
                    </text>
                  </title>
                  <data key="case_type" ref="'case'"/>
                  <prompt key="name">
                    <display>
                      <text>
                        <locale id="search_property.m0.name"/>
                      </text>
                    </display>
                  </prompt>
                </query>
                <datum id="case_id" nodeset="instance('{RESULTS_INSTANCE_INLINE}')/results/case[@case_type='case'][@status='open'][active = 'yes'][not(commcare_is_related_case=true())]"
                    value="./@case_id" detail-select="m0_case_short" detail-confirm="m0_case_long"/>
            </session>
          </entry>
        </partial>"""  # noqa: E501
        self.assertXmlPartialEqual(expected_entry_query, suite, "./entry[2]")

    @flag_enabled('USH_SEARCH_FILTER')
    def test_inline_search_multi_select(self):
        self.module.case_details.short.multi_select = True
        self.module.case_details.short.columns.append(
            DetailColumn.wrap(dict(
                header={"en": "parent name"},
                model="case",
                format="plain",
                field="parent/name"
            ))
        )
        suite = self.app.create_suite()

        expected_entry_query = f"""
        <partial>
          <entry>
            <form>xmlns1.0</form>
            <post url="http://localhost:8000/a/test_domain/phone/claim-case/"
                relevant="$case_id != ''">
             <data exclude="count(instance('casedb')/casedb/case[@case_id=current()/.]) = 1"
                key="case_id" nodeset="instance('selected_cases')/results/value" ref="."/>
            </post>
            <command id="m0-f0">
              <text>
                <locale id="forms.m0f0"/>
              </text>
            </command>
            <instance id="casedb" src="jr://instance/casedb"/>
            <instance id="results:inline" src="jr://instance/remote/results:inline"/>
            <instance id="selected_cases" src="jr://instance/selected-entities/selected_cases"/>
            <session>
                <query url="http://localhost:8000/a/test_domain/phone/search/123/"
                    storage-instance="{RESULTS_INSTANCE_INLINE}"
                    template="case" default_search="false">
                  <title>
                    <text>
                        <locale id="case_search.m0.inputs"/>
                    </text>
                  </title>
                  <data key="case_type" ref="'case'"/>
                  <prompt key="name">
                    <display>
                      <text>
                        <locale id="search_property.m0.name"/>
                      </text>
                    </display>
                  </prompt>
                </query>
                <instance-datum id="selected_cases" nodeset="instance('{RESULTS_INSTANCE_INLINE}')/results/case[@case_type='case'][@status='open'][active = 'yes'][not(commcare_is_related_case=true())]"
                    value="./@case_id" detail-select="m0_case_short" detail-confirm="m0_case_long" max-select-value="100"/>
            </session>
          </entry>
        </partial>"""  # noqa: E501
        self.assertXmlPartialEqual(expected_entry_query, suite, "./entry[1]")

        expected_detail_columns = f"""
        <partial>
          <xpath function="case_name"/>
          <xpath function="instance('{RESULTS_INSTANCE_INLINE}')/results/case[@case_id=current()/index/parent]/case_name"/>
        </partial>"""  # noqa: E501
        self.assertXmlPartialEqual(
            expected_detail_columns, suite, "./detail[@id='m0_case_short']/field/template/text/xpath")

    def test_case_detail_tabs_with_inline_search(self):
        """Test that the detail nodeset uses the correct instance (results:inline not casedb)"""
        self.app.get_module(0).case_details.long.tabs = [
            DetailTab(starting_index=0),
            DetailTab(starting_index=1, has_nodeset=True, nodeset_case_type="child")
        ]

        self.assertXmlPartialEqual(
            self.get_xml("detail_tabs"),
            self.app.create_suite(),
            './detail[@id="m0_case_long"]')

    def test_form_linking_to_inline_search_module_from_registration_form(self):
        self.module.search_config.additional_case_types = ["other_case"]
        suite = self.app.create_suite()
        expected = f"""
        <partial>
          <create>
            <command value="'m0'"/>
            <query id="{RESULTS_INSTANCE_INLINE}" value="http://localhost:8000/a/test_domain/phone/case_fixture/123/">
              <data key="case_type" ref="'case'"/>
              <data key="case_type" ref="'other_case'"/>
              <data key="case_id" ref="instance('commcaresession')/session/data/case_id_new_case_0"/>
            </query>
            <datum id="case_id" value="instance('commcaresession')/session/data/case_id_new_case_0"/>
            <command value="'m0-f0'"/>
          </create>
        </partial>"""  # noqa: E501
        self.assertXmlPartialEqual(
            expected,
            suite,
            "./entry[2]/stack/create"
        )

    def test_workflow_inline_search_previous_screen_after_case_list_form(self):
        factory = AppFactory(DOMAIN, "App with DR", build_version='2.53.0')
        m0, f0 = factory.new_basic_module("new case", "case")
        factory.form_opens_case(f0, "case")

        m1, f1 = factory.new_basic_module("update case", "case")
        factory.form_requires_case(f1, "case")

        m1.case_details.long.columns.append(
            DetailColumn.wrap(dict(
                header={"en": "name"},
                model="case",
                format="plain",
                field="whatever",
            ))
        )

        m1.search_config = CaseSearch(
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
            ],
            auto_launch=True,
            inline_search=True,
        )

        m1.case_list_form.form_id = f0.get_unique_id()
        m1.case_list_form.label = {'en': 'New Case'}

        f1.post_form_workflow = WORKFLOW_PREVIOUS
        app = Application.wrap(factory.app.to_json())
        app._id = "123"
        suite = app.create_suite()
        self.assertXmlPartialEqual(
            f"""
            <partial>
              <create>
                <command value="'m1'"/>
                <query id="{RESULTS_INSTANCE_INLINE}" value="http://localhost:8000/a/test_domain/phone/case_fixture/123/">
                  <data key="case_type" ref="'case'"/>
                  <data key="case_id" ref="instance('commcaresession')/session/data/case_id"/>
                </query>
                <datum id="case_id" value="instance('commcaresession')/session/data/case_id"/>
              </create>
            </partial>
            """,  # noqa: E501
            suite,
            "./entry[2]/stack/create"
        )

    @flag_enabled('MOBILE_UCR')
    def test_prompt_itemset_mobile_report(self):
        self.module.search_config.properties[0].input_ = 'select1'
        instance_id = "commcare-reports:123abc"
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
        self.assertXmlPartialEqual(expected, suite, "./entry[1]/session/query/prompt[@key='name']")

        expected_instance = f"""
            <partial>
              <instance id="{instance_id}" src="jr://fixture/commcare-reports:123abc"/>
            </partial>
            """
        self.assertXmlPartialEqual(
            expected_instance,
            suite,
            f"./entry[1]/instance[@id='{instance_id}']",
        )

    @flag_enabled('USH_SEARCH_FILTER')
    def test_inline_search_with_parent_select(self):
        """Inline search module can have 'parent select' as long as the
        relationship is 'other' (None).
        Inline search modules can never be the parent select module.
          * post requests aren't included in the entries for the module with parent select
          * parent filtering doesn't work since the 'case claim' isn't triggered before filtering
        """
        module = self.app.add_module(Module.new_module("Followup2", None))
        form = self.app.new_form(2, "Untitled Form", None, attachment=get_simple_form("xmlns1.0"))
        form.requires = 'case'
        module.case_type = 'case'

        self.module.parent_select.active = True
        self.module.parent_select.relationship = None
        self.module.parent_select.module_id = module.unique_id

        suite = self.app.create_suite()

        expected_entry = f"""
        <partial>
          <entry>
            <form>xmlns1.0</form>
            <post url="http://localhost:8000/a/test_domain/phone/claim-case/"
                relevant="count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]) = 0">
              <data key="case_id" ref="instance('commcaresession')/session/data/case_id"/>
            </post>
            <command id="m0-f0">
              <text>
                <locale id="forms.m0f0"/>
              </text>
            </command>
            <instance id="casedb" src="jr://instance/casedb"/>
            <instance id="commcaresession" src="jr://instance/session"/>
            <instance id="results:inline" src="jr://instance/remote/results:inline"/>
            <session>
              <datum id="case_id_case"
                nodeset="instance('casedb')/casedb/case[@case_type='case'][@status='open']"
                value="./@case_id" detail-select="m2_case_short"/>
              <query url="http://localhost:8000/a/test_domain/phone/search/123/"
                storage-instance="{RESULTS_INSTANCE_INLINE}" template="case" default_search="false">
                <title>
                  <text>
                      <locale id="case_search.m0.inputs"/>
                  </text>
                </title>
                <data key="case_type" ref="'case'"/>
                <prompt key="name">
                  <display>
                    <text>
                      <locale id="search_property.m0.name"/>
                    </text>
                  </display>
                </prompt>
              </query>
              <datum id="case_id"
                nodeset="instance('{RESULTS_INSTANCE_INLINE}')/results/case[@case_type='case'][@status='open'][active = 'yes'][not(commcare_is_related_case=true())]"
                value="./@case_id" detail-select="m0_case_short" detail-confirm="m0_case_long"/>
            </session>
          </entry>
        </partial>"""  # noqa: E501

        self.assertXmlPartialEqual(expected_entry, suite, "./entry[1]")


@patch_get_xform_resource_overrides()
class InlineSearchShadowModuleTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite_inline_search')

    def setUp(self):
        self.app = Application.new_app(DOMAIN, "Application with Shadow")
        self.app._id = '456'
        self.app.build_spec = BuildSpec(version='2.53.0', build_number=1)
        self.module = self.app.add_module(Module.new_module("Followup", None))
        self.form = self.app.new_form(0, "Untitled Form", None, attachment=get_simple_form("xmlns1.0"))
        self.form.requires = 'case'
        self.module.case_type = 'case'

        self.module.case_details.long.columns.append(
            DetailColumn.wrap(dict(
                header={"en": "name"},
                model="case",
                format="plain",
                field="whatever",
            ))
        )

        self.module.search_config = CaseSearch(
            properties=[CaseSearchProperty(name='name', label={'en': 'Name'})],
            auto_launch=True,
            inline_search=True,
        )

        self.shadow_module = self.app.add_module(ShadowModule.new_module("Shadow", "en"))
        self.shadow_module.source_module_id = self.module.unique_id

        self.shadow_module.case_details.long.columns.append(
            DetailColumn.wrap(dict(
                header={"en": "name"},
                model="case",
                format="plain",
                field="whatever",
            ))
        )

        self.shadow_module.search_config = CaseSearch(
            properties=[CaseSearchProperty(name='name', label={'en': 'Name'})],
            auto_launch=True,
            inline_search=True,
        )

        # wrap to have assign_references called
        self.app = Application.wrap(self.app.to_json())

        # reset to newly wrapped module
        self.module = self.app.modules[0]
        self.shadow_module = self.app.modules[1]

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
    def test_suite(self):
        suite = self.app.create_suite()
        self.assertXmlPartialEqual(
            self.get_xml('shadow_module_entry'),
            suite,
            "./entry[2]"
        )

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
    def test_additional_types(self):
        another_case_type = "another_case_type"
        self.module.search_config.additional_case_types = [another_case_type]
        suite_xml = self.app.create_suite()
        suite = parse_normalize(suite_xml, to_string=False)
        self.assertEqual(
            "instance('{}')/{}/case[@case_type='{}' or @case_type='{}'][@status='open']{}".format(
                RESULTS_INSTANCE_INLINE,
                "results",
                self.module.case_type,
                another_case_type,
                EXCLUDE_RELATED_CASES_FILTER
            ),
            suite.xpath("./entry[2]/session/datum/@nodeset")[0]
        )
        self.assertXmlPartialEqual(
            """
            <partial>
              <data key="case_type" ref="'case'"/>
              <data key="case_type" ref="'another_case_type'"/>
            </partial>
            """,
            suite_xml,
            "./entry[2]/session/query[1]/data[@key='case_type']"
        )


@patch_get_xform_resource_overrides()
class InlineSearchChildModuleTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite_inline_search')

    def setUp(self):
        factory = AppFactory(DOMAIN, "App with inline search and child modules", build_version='2.53.0')
        m0, f0 = factory.new_basic_module("case list", "case")
        factory.form_requires_case(f0)

        m1, f1 = factory.new_basic_module("child case list", "case", parent_module=m0)
        m1.parent_select = ParentSelect(active=True, relationship=None, module_id=m0.get_or_create_unique_id())
        f2 = factory.new_form(m1)

        factory.form_requires_case(f1)
        factory.form_requires_case(f2)

        m1.search_config = CaseSearch(
            properties=[CaseSearchProperty(name='name', label={'en': 'Name'})],
            auto_launch=True,
            inline_search=True,
        )

        factory.app._id = "123"
        # wrap to have assign_references called
        self.app = Application.wrap(factory.app.to_json())

    def test_child_module_with_inline_search_entry(self):
        """An inline search module can be a child module
            * as long as there is no parent selection or parent_select.relationship = None

        An inline search module can never be a parent module
          * post requests aren't included in the entries for the child module
        """
        suite = self.app.create_suite()

        expected_entry = f"""
        <partial>
          <entry>
            <post url="http://localhost:8000/a/test_domain/phone/claim-case/"
                relevant="count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id_case]) = 0">
              <data key="case_id" ref="instance('commcaresession')/session/data/case_id_case"/>
            </post>
            <command id="m1-f0">
              <text>
                <locale id="forms.m1f0"/>
              </text>
            </command>
            <instance id="casedb" src="jr://instance/casedb"/>
            <instance id="commcaresession" src="jr://instance/session"/>
            <instance id="results:inline" src="jr://instance/remote/results:inline"/>
            <session>
              <datum id="case_id" nodeset="instance('casedb')/casedb/case[@case_type='case'][@status='open']"
                value="./@case_id" detail-select="m0_case_short"/>
              <query url="http://localhost:8000/a/test_domain/phone/search/123/"
                storage-instance="{RESULTS_INSTANCE_INLINE}" template="case" default_search="false">
                <title>
                  <text>
                      <locale id="case_search.m1.inputs"/>
                  </text>
                </title>
                <data key="case_type" ref="'case'"/>
                <prompt key="name">
                  <display>
                    <text>
                      <locale id="search_property.m1.name"/>
                    </text>
                  </display>
                </prompt>
              </query>
              <datum id="case_id_case"
                nodeset="instance('{RESULTS_INSTANCE_INLINE}')/results/case[@case_type='case'][@status='open'][not(commcare_is_related_case=true())]"
                value="./@case_id" detail-select="m1_case_short" detail-confirm="m1_case_long"/>
            </session>
          </entry>
        </partial>
        """  # noqa: E501
        self.assertXmlPartialEqual(expected_entry, suite, "./entry[2]")

    def test_form_link_in_child_module_with_inline_search(self):
        module = self.app.get_module(1)
        form1 = module.get_form(0)
        form2 = module.get_form(1)
        # link from f1 to f2 (both in the child module)
        form1.post_form_workflow = WORKFLOW_FORM
        form1.form_links = [FormLink(form_id=form2.get_unique_id(), form_module_id=module.unique_id)]
        suite = self.app.create_suite()
        expected = f"""
        <partial>
          <create>
            <command value="'m0'"/>
            <datum id="case_id" value="instance('commcaresession')/session/data/case_id"/>
            <command value="'m1'"/>
            <query id="{RESULTS_INSTANCE_INLINE}" value="http://localhost:8000/a/test_domain/phone/case_fixture/123/">
              <data key="case_type" ref="'case'"/>
              <data key="case_id" ref="instance('commcaresession')/session/data/case_id_case"/>
            </query>
            <datum id="case_id_case" value="instance('commcaresession')/session/data/case_id_case"/>
            <command value="'m1-f1'"/>
          </create>
        </partial>"""  # noqa: E501

        self.assertXmlPartialEqual(expected, suite, "./entry[2]/stack/create")
