from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    Application,
    CaseSearch,
    CaseSearchProperty,
    DetailColumn,
    Module,
)
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    TestXmlMixin,
    get_simple_form,
    patch_get_xform_resource_overrides,
)
from corehq.apps.builds.models import BuildSpec
from corehq.util.test_utils import flag_enabled

DOMAIN = 'test_domain'


@patch_get_xform_resource_overrides()
class InlineSearchSuiteTest(SimpleTestCase, TestXmlMixin, SuiteMixin):
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
            auto_launch=True,
            inline_search=True,
        )

        self.module.assign_references()
        # reset to newly wrapped module
        self.module = self.app.modules[0]
        self.form = self.module.forms[0]

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
    def test_inline_search(self, *args):
        suite = self.app.create_suite()

        expected_entry_query = """
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
            <session>
                <query url="http://localhost:8000/a/test_domain/phone/search/123/" storage-instance="results"
                    template="case" default_search="false">
                  <data key="case_type" ref="'case'"/>
                  <prompt key="name">
                    <display>
                      <text>
                        <locale id="search_property.m0.name"/>
                      </text>
                    </display>
                  </prompt>
                </query>
                <datum id="case_id" nodeset="instance('results')/results/case[@case_type='case'][@status='open'][not(commcare_is_related_case=true())]"
                    value="./@case_id" detail-select="m0_case_short" detail-confirm="m0_case_long"/>
            </session>
          </entry>
        </partial>"""  # noqa: E501
        self.assertXmlPartialEqual(expected_entry_query, suite, "./entry[1]")

        self.assertXmlDoesNotHaveXpath(suite, "./detail[@id='m0_case_short']/action/display/text/locale")
        self.assertXmlDoesNotHaveXpath(suite, "./remote-request")
        self.assertXmlDoesNotHaveXpath(suite, "./detail[@id='m0_search_short']")
        self.assertXmlDoesNotHaveXpath(suite, "./detail[@id='m0_search_long']")
