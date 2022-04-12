from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    CaseSearch,
    CaseSearchLabel,
    CaseSearchProperty,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    TestXmlMixin,
    patch_get_xform_resource_overrides,
)
from corehq.util.test_utils import flag_enabled

from .util import patch_validate_xform


@patch('corehq.util.view_utils.get_url_base', new=lambda: "https://www.example.com")
@patch_validate_xform()
@patch_get_xform_resource_overrides()
@flag_enabled('USH_CASE_LIST_MULTI_SELECT')
class MultiSelectCaseListTests(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        self.factory = AppFactory(domain="multiple-referrals")
        self.app_id = uuid4().hex
        self.factory.app._id = self.app_id
        self.module, form = self.factory.new_basic_module('basic', 'person')
        self.factory.form_requires_case(form, 'person')
        form.xmlns = "some-xmlns"

        self.module.case_details.short.multi_select = True
        self.module.search_config = CaseSearch(
            search_label=CaseSearchLabel(label={'en': 'Search'}),
            properties=[CaseSearchProperty(name=field) for field in ['name', 'greatest_fear']],
        )
        self.module.assign_references()

    def test_multi_select_case_list(self):
        suite = self.factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
              <entry>
                <form>some-xmlns</form>
                <command id="m0-f0">
                  <text>
                    <locale id="forms.m0f0"/>
                  </text>
                </command>
                <instance id="casedb" src="jr://instance/casedb"/>
                <session>
                  <instance-datum id="case_id"
                                  nodeset="instance('casedb')/casedb/case[@case_type='person'][@status='open']"
                                  value="./@case_id"
                                  detail-select="m0_case_short"
                                  detail-confirm="m0_case_long"/>
                </session>
              </entry>
            </partial>
            """,
            suite,
            "./entry",
        )
        self.assertXmlPartialEqual(
            self.get_xml('multi_select_case_list').decode('utf-8').format(app_id=self.factory.app._id),
            suite,
            "./remote-request",
        )

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
    def test_multi_select_case_list_auto_launch(self):
        self.module.search_config.auto_launch = True
        suite = self.factory.app.create_suite()

        self.assertXmlPartialEqual(
            """
            <partial>
              <action auto_launch="true()" redo_last="false">
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
            """,
            suite,
            "./detail[@id='m0_case_short']/action",
        )

        self.assertXmlPartialEqual(
            """
            <partial>
              <action auto_launch="false()" redo_last="true">
                <display>
                  <text>
                    <locale id="case_search.m0.again"/>
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
            """,
            suite,
            "./detail[@id='m0_search_short']/action",
        )

        self.module.search_config.auto_launch = False
