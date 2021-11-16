from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.apps.app_manager.const import WORKFLOW_FORM
from corehq.apps.app_manager.models import (
    Application,
    CaseSearch,
    CaseSearchProperty,
    Itemset,
    Module,
    DetailColumn,
    FormLink,
    DetailTab,
)
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    TestXmlMixin,
    patch_get_xform_resource_overrides, get_simple_form,
)
from corehq.apps.builds.models import BuildSpec
from corehq.util.test_utils import flag_enabled

DOMAIN = 'test_domain'


@patch_get_xform_resource_overrides()
@patch.object(Application, 'supports_data_registry', lambda: True)
class RemoteRequestSuiteTest(SimpleTestCase, TestXmlMixin, SuiteMixin):
    file_path = ('data', 'suite_registry')

    def setUp(self):
        self.app = Application.new_app(DOMAIN, "Untitled Application")
        self.app._id = '123'
        self.app.build_spec = BuildSpec(version='2.35.0', build_number=1)
        self.module = self.app.add_module(Module.new_module("Untitled Module", None))
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
                CaseSearchProperty(name='favorite_color', label={'en': 'Favorite Color'}, itemset=Itemset(
                    instance_id='colors', instance_uri='jr://fixture/item-list:colors',
                    nodeset="instance('colors')/colors_list/colors", label='name', sort='name', value='value'),
                )
            ],
            data_registry="myregistry"
        )

        # wrap to have assign_references called
        self.app = Application.wrap(self.app.to_json())
        # reset to newly wrapped module
        self.module = self.app.modules[0]
        self.form = self.module.forms[0]

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
    def test_search_data_registry(self, *args):
        suite = self.app.create_suite()

        expected_entry_query = """
        <partial>
          <session>
            <query url="http://localhost:8000/a/test_domain/phone/search/123/" storage-instance="results"
                template="case" default_search="false">
              <data key="case_type" ref="'case'"/>
              <data key="commcare_registry" ref="'myregistry'"/>
              <prompt key="name">
                <display>
                  <text>
                    <locale id="search_property.m0.name"/>
                  </text>
                </display>
              </prompt>
              <prompt key="favorite_color">
                <display>
                  <text>
                    <locale id="search_property.m0.favorite_color"/>
                  </text>
                </display>
                <itemset nodeset="instance('colors')/colors_list/colors">
                  <label ref="name"/>
                  <value ref="value"/>
                  <sort ref="name"/>
                </itemset>
              </prompt>
            </query>
            <datum id="case_id" nodeset="instance('results')/results/case[@case_type='case'][@status='open']"
                value="./@case_id" detail-select="m0_case_short" detail-confirm="m0_case_long"/>
            <query url="http://localhost:8000/a/test_domain/phone/registry_case/123/"
                storage-instance="registry" template="case" default_search="true">
              <data key="commcare_registry" ref="'myregistry'"/>
              <data key="case_type" ref="'case'"/>
              <data key="case_id" ref="instance('commcaresession')/session/data/case_id"/>
            </query>
          </session>
        </partial>"""
        self.assertXmlPartialEqual(expected_entry_query, suite, "./entry[1]/session")

        # assert that session instance is added to the entry
        self.assertXmlHasXpath(suite, "./entry[1]/instance[@id='commcaresession']")

        # needed for 'search again' workflow
        self.assertXmlPartialEqual(
            """<partial>
                <locale id="case_search.m0.again"/>
            </partial>""",
            suite,
            "./detail[@id='m0_case_short']/action/display/text/locale"
        )
        self.assertXmlHasXpath(suite, "./remote-request")
        self.assertXmlHasXpath(suite, "./detail[@id='m0_search_short']")
        self.assertXmlHasXpath(suite, "./detail[@id='m0_search_long']")

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
    def test_search_data_registry_additional_registry_query(self, *args):
        base_xpath = "instance('registry')/results/case[@case_id=instance('commcaresession')/session/data/case_id]"
        self.module.search_config.additional_case_types = ["other_case"]
        self.module.search_config.additional_registry_cases = [
            f"{base_xpath}/potential_duplicate_case_id"
        ]
        suite = self.app.create_suite()

        expected_entry_query = f"""
        <partial>
          <query url="http://localhost:8000/a/test_domain/phone/registry_case/123/" storage-instance="registry"
                template="case" default_search="true">
            <data key="commcare_registry" ref="'myregistry'"/>
            <data key="case_type" ref="'case'"/>
            <data key="case_type" ref="'other_case'"/>
            <data key="case_id" ref="instance('commcaresession')/session/data/case_id"/>
            <data key="case_id" ref="{base_xpath}/potential_duplicate_case_id"/>
          </query>
        </partial>"""
        self.assertXmlPartialEqual(expected_entry_query, suite, "./entry[1]/session/query[2]")

        self.assertXmlHasXpath(suite, "./entry[1]/instance[@id='commcaresession']")
        self.assertXmlDoesNotHaveXpath(suite, "./entry[1]/instance[@id='registry']")

    def test_form_linking_with_registry_module(self, *args):
        self.form.post_form_workflow = WORKFLOW_FORM
        self.form.form_links = [
            FormLink(xpath="(today() - dob) &lt; 7", module_unique_id=self.module.unique_id)
        ]
        self.assertXmlPartialEqual(
            self.get_xml('form_link_followup_module_registry'),
            self.app.create_suite(),
            "./entry[1]"
        )

    def test_case_detail_tabs_with_registry_module(self, *args):
        self.app.get_module(0).case_details.long.tabs = [
            DetailTab(starting_index=1)
        ]

        self.assertXmlPartialEqual(
            self.get_xml("detail_tabs"),
            self.app.create_suite(),
            './detail[@id="m0_case_long"]')
