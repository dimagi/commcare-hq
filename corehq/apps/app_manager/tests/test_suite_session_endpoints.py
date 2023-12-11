from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.apps.app_manager.const import REGISTRY_WORKFLOW_LOAD_CASE, REGISTRY_WORKFLOW_SMART_LINK
from corehq.apps.app_manager.models import (
    LoadCaseFromFixture,
    LoadUpdateAction,
    CaseSearch,
    CaseSearchProperty
)
from corehq.apps.app_manager.xform_builder import XFormBuilder
from corehq.util.test_utils import flag_enabled

from .app_factory import AppFactory
from .util import (
    TestXmlMixin,
    patch_get_xform_resource_overrides,
    patch_validate_xform,
)


@patch_validate_xform()
@patch_get_xform_resource_overrides()
@flag_enabled('SESSION_ENDPOINTS')
class SessionEndpointTests(SimpleTestCase, TestXmlMixin):
    file_path = ('data',)

    def setUp(self):
        self.domain = 'test-domain'
        self.factory = AppFactory(build_version='2.51.0', domain=self.domain)
        self.parent_case_type = 'mother'
        self.child_case_type = 'baby'
        self.module, self.form = self.factory.new_basic_module('basic', self.parent_case_type)
        self.child_module, self.child_module_form = self.factory.new_basic_module(
            'child', self.child_case_type, parent_module=self.module,
        )

        builder = XFormBuilder(self.form.name)
        builder.new_question(name='name', label='Name')
        self.form.source = builder.tostring(pretty_print=True).decode('utf-8')

    def test_empty_string_yields_no_endpoint(self):
        self.form.session_endpoint_id = ''
        self.assertXmlDoesNotHaveXpath(
            self.factory.app.create_suite(),
            "./endpoint",
        )

    def test_multi_case_list_module_session_endpoint_id(self):
        self.module.session_endpoint_id = 'case_list'
        self.factory.form_requires_case(self.form, case_type=self.parent_case_type)
        self.module.case_details.short.multi_select = True
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
           <partial>
                <endpoint id="case_list">
                    <argument id="selected_cases" instance-id="selected_cases"
                        instance-src="jr://instance/selected-entities"/>
                    <stack>
                        <push>
                            <instance-datum id="selected_cases" value="$selected_cases"/>
                            <command value="'claim_command.case_list.selected_cases'"/>
                        </push>
                        <push>
                            <command value="'m0'"/>
                            <instance-datum id="selected_cases" value="$selected_cases"/>
                        </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            self.factory.app.create_suite(),
            "./endpoint",
        )
        self.assertXmlPartialEqual(
            self.get_xml("session_endpoint_remote_request_multi_select").decode('utf-8').format(
                datum_id="selected_cases",
                endpoint_id="case_list",
            ),
            suite,
            "./remote-request",
        )

    def test_case_list_module_session_endpoint_id(self):
        self.module.session_endpoint_id = 'case_list'
        self.factory.form_requires_case(self.form, case_type=self.parent_case_type)
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
           <partial>
                <endpoint id="case_list">
                    <argument id="case_id"/>
                    <stack>
                        <push>
                            <datum id="case_id" value="$case_id"/>
                            <command value="'claim_command.case_list.case_id'"/>
                        </push>
                        <push>
                            <command value="'m0'"/>
                            <datum id="case_id" value="$case_id"/>
                        </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            self.factory.app.create_suite(),
            "./endpoint",
        )
        self.assertXmlPartialEqual(
            self.get_xml("session_endpoint_remote_request").decode('utf-8').format(
                datum_id="case_id",
                endpoint_id="case_list",
            ),
            suite,
            "./remote-request",
        )

    def test_case_list_module_case_list_session_endpoint_id(self):
        self.module.case_list_session_endpoint_id = 'case_list'
        self.factory.form_requires_case(self.form, case_type=self.parent_case_type)
        self.assertXmlPartialEqual(
            """
           <partial>
                <endpoint id="case_list">
                    <stack>
                        <push>
                            <command value="'m0'"/>
                        </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            self.factory.app.create_suite(),
            "./endpoint",
        )

    def test_registration_form_session_endpoint_id(self):
        self.form.session_endpoint_id = 'my_form'
        self.factory.form_opens_case(self.form, case_type=self.parent_case_type)
        self.assertXmlPartialEqual(
            """
            <partial>
                <endpoint id="my_form">
                    <stack>
                        <push>
                            <command value="'m0'"/>
                            <command value="'m0-f0'"/>
                        </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            self.factory.app.create_suite(),
            "./endpoint",
        )

    def test_followup_form_session_endpoint_id(self):
        self.form.session_endpoint_id = 'my_form'
        self.factory.form_requires_case(self.form, case_type=self.parent_case_type)
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
                <endpoint id="my_form">
                    <argument id="case_id"/>
                    <stack>
                        <push>
                            <datum id="case_id" value="$case_id"/>
                            <command value="'claim_command.my_form.case_id'"/>
                        </push>
                        <push>
                            <command value="'m0'"/>
                            <datum id="case_id" value="$case_id"/>
                            <command value="'m0-f0'"/>
                        </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            suite,
            "./endpoint",
        )
        self.assertXmlPartialEqual(
            self.get_xml("session_endpoint_remote_request").decode('utf-8').format(
                datum_id="case_id",
                endpoint_id="my_form",
            ),
            suite,
            "./remote-request",
        )

    def test_child_case_list_session_endpoint_id(self):
        self.child_module.session_endpoint_id = 'child_case_list'
        self.factory.form_requires_case(
            self.child_module_form,
            case_type=self.child_case_type,
            parent_case_type=self.parent_case_type
        )
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.factory.app.create_suite()

        self.assertXmlPartialEqual(
            """
            <partial>
                <endpoint id="child_case_list">
                    <argument id="parent_id"/>
                    <argument id="case_id"/>
                    <stack>
                        <push>
                            <datum id="parent_id" value="$parent_id"/>
                            <command value="'claim_command.child_case_list.parent_id'"/>
                        </push>
                        <push>
                            <datum id="case_id" value="$case_id"/>
                            <command value="'claim_command.child_case_list.case_id'"/>
                        </push>
                        <push>
                            <command value="'m0'"/>
                            <command value="'m1'"/>
                            <datum id="parent_id" value="$parent_id"/>
                            <datum id="case_id" value="$case_id"/>
                        </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            suite,
            "./endpoint",
        )

        self.assertXmlPartialEqual(
            self.get_xml("session_endpoint_remote_request").decode('utf-8').format(
                datum_id="parent_id",
                endpoint_id="child_case_list",
            ),
            suite,
            "./remote-request[1]",
        )
        self.assertXmlPartialEqual(
            self.get_xml("session_endpoint_remote_request").decode('utf-8').format(
                datum_id="case_id",
                endpoint_id="child_case_list",
            ),
            suite,
            "./remote-request[2]",
        )

    def test_child_case_list_module_case_list_session_endpoint_id(self):
        self.child_module.case_list_session_endpoint_id = 'child_case_list'
        self.factory.form_requires_case(
            self.child_module_form,
            case_type=self.child_case_type,
            parent_case_type=self.parent_case_type
        )
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.factory.app.create_suite()

        self.assertXmlPartialEqual(
            """
            <partial>
                <endpoint id="child_case_list">
                    <argument id="parent_id"/>
                    <stack>
                        <push>
                            <datum id="parent_id" value="$parent_id"/>
                            <command value="'claim_command.child_case_list.parent_id'"/>
                        </push>
                        <push>
                            <command value="'m0'"/>
                            <command value="'m1'"/>
                            <datum id="parent_id" value="$parent_id"/>
                        </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            suite,
            "./endpoint",
        )

        self.assertXmlPartialEqual(
            self.get_xml("session_endpoint_remote_request").decode('utf-8').format(
                datum_id="parent_id",
                endpoint_id="child_case_list",
            ),
            suite,
            "./remote-request",
        )

    def test_child_module_form_session_endpoint_id(self):
        self.child_module_form.session_endpoint_id = 'my_form'
        self.factory.form_requires_case(
            self.child_module_form,
            case_type=self.child_case_type,
            parent_case_type=self.parent_case_type
        )
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.factory.app.create_suite()

        self.assertXmlPartialEqual(
            """
            <partial>
                <endpoint id="my_form">
                    <argument id="parent_id"/>
                    <argument id="case_id"/>
                    <stack>
                        <push>
                            <datum id="parent_id" value="$parent_id"/>
                            <command value="'claim_command.my_form.parent_id'"/>
                        </push>
                        <push>
                            <datum id="case_id" value="$case_id"/>
                            <command value="'claim_command.my_form.case_id'"/>
                        </push>
                        <push>
                            <command value="'m0'"/>
                            <command value="'m1'"/>
                            <datum id="parent_id" value="$parent_id"/>
                            <datum id="case_id" value="$case_id"/>
                            <command value="'m1-f0'"/>
                        </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            suite,
            "./endpoint",
        )

        self.assertXmlPartialEqual(
            self.get_xml("session_endpoint_remote_request").decode('utf-8').format(
                datum_id="parent_id",
                endpoint_id="my_form",
            ),
            suite,
            "./remote-request[1]",
        )
        self.assertXmlPartialEqual(
            self.get_xml("session_endpoint_remote_request").decode('utf-8').format(
                datum_id="case_id",
                endpoint_id="my_form",
            ),
            suite,
            "./remote-request[2]",
        )

    def test_multiple_session_endpoints(self):
        self.form.session_endpoint_id = 'my_form'
        self.child_module_form.session_endpoint_id = 'my_child_form'
        self.factory.form_requires_case(
            self.child_module_form,
            case_type=self.child_case_type,
            parent_case_type=self.parent_case_type
        )
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.factory.app.create_suite()

        self.assertXmlPartialEqual(
            """
            <partial>
                <endpoint id="my_form">
                    <stack>
                        <push>
                            <command value="'m0'"/>
                            <command value="'m0-f0'"/>
                        </push>
                    </stack>
                </endpoint>
                <endpoint id="my_child_form">
                    <argument id="parent_id"/>
                    <argument id="case_id"/>
                    <stack>
                        <push>
                            <datum id="parent_id" value="$parent_id"/>
                            <command value="'claim_command.my_child_form.parent_id'"/>
                        </push>
                        <push>
                            <datum id="case_id" value="$case_id"/>
                            <command value="'claim_command.my_child_form.case_id'"/>
                        </push>
                        <push>
                            <command value="'m0'"/>
                            <command value="'m1'"/>
                            <datum id="parent_id" value="$parent_id"/>
                            <datum id="case_id" value="$case_id"/>
                            <command value="'m1-f0'"/>
                        </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            suite,
            "./endpoint",
        )

        self.assertXmlPartialEqual(
            self.get_xml("session_endpoint_remote_request").decode('utf-8').format(
                datum_id="parent_id",
                endpoint_id="my_child_form",
            ),
            suite,
            "./remote-request[1]",
        )
        self.assertXmlPartialEqual(
            self.get_xml("session_endpoint_remote_request").decode('utf-8').format(
                datum_id="case_id",
                endpoint_id="my_child_form",
            ),
            suite,
            ".remote-request[2]",
        )

    def test_registry_workflows(self):
        self.module.session_endpoint_id = 'my_case_list'

        with patch("corehq.apps.app_manager.util.module_offers_search") as mock:
            mock.return_value = True
            self.module.search_config.data_registry_workflow = REGISTRY_WORKFLOW_SMART_LINK
            self.assertXmlPartialEqual(
                """
                <partial>
                    <endpoint id="my_case_list">
                        <stack>
                            <push>
                                <command value="'m0'"/>
                            </push>
                        </stack>
                    </endpoint>
                </partial>
                """,
                self.factory.app.create_suite(),
                "./endpoint",
            )

            self.module.search_config.data_registry_workflow = REGISTRY_WORKFLOW_LOAD_CASE
            self.assertXmlPartialEqual(
                """
                <partial>
                    <endpoint id="my_case_list">
                        <stack>
                            <push>
                                <command value="'m0'"/>
                            </push>
                        </stack>
                    </endpoint>
                </partial>
                """,
                self.factory.app.create_suite(),
                "./endpoint",
            )

    def test_module_session_endpoint_id(self):
        self.module.session_endpoint_id = 'my_case_list'
        self.assertXmlPartialEqual(
            """
            <partial>
                <endpoint id="my_case_list">
                    <stack>
                        <push>
                            <command value="'m0'"/>
                        </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            self.factory.app.create_suite(),
            "./endpoint",
        )

    def test_child_module_session_endpoint_id(self):
        self.child_module.session_endpoint_id = 'my_child_module'
        self.assertXmlPartialEqual(
            """
            <partial>
                <endpoint id="my_child_module">
                    <stack>
                        <push>
                            <command value="'m0'"/>
                            <command value="'m1'"/>
                        </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            self.factory.app.create_suite(),
            "./endpoint",
        )

    def test_inline_case_search_list_module_session_endpoint_id(self):
        self.module.session_endpoint_id = 'case_list'
        self.factory.form_requires_case(self.form, case_type=self.parent_case_type)
        self.module.search_config = CaseSearch(
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
            ],
            search_filter="active = 'yes'",
            auto_launch=True,
            inline_search=True,
        )
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            self.factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
           <partial>
                <endpoint id="case_list">
                    <argument id="case_id"/>
                    <stack>
                        <push>
                             <command value="'m0'"/>
                             <query id="results:inline"
                                value="http://localhost:8000/a/test-domain/phone/case_fixture/None/">
                               <data key="case_type" ref="'mother'"/>
                               <data key="case_id" ref="$case_id"/>
                             </query>
                            <datum id="case_id" value="$case_id"/>
                        </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            self.factory.app.create_suite(),
            "./endpoint",
        )

    def test_inline_case_search_multi_list_module_session_endpoint_id(self):
        self.module.session_endpoint_id = 'case_list'
        self.factory.form_requires_case(self.form, case_type=self.parent_case_type)
        self.module.case_details.short.multi_select = True
        self.module.search_config = CaseSearch(
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
            ],
            search_filter="active = 'yes'",
            auto_launch=True,
            inline_search=True,
        )
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            self.factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
           <partial>
                <endpoint id="case_list">
                    <argument id="selected_cases" instance-id="selected_cases"
                        instance-src="jr://instance/selected-entities"/>
                    <stack>
                        <push>
                             <command value="'m0'"/>
                             <query id="results:inline"
                                value="http://localhost:8000/a/test-domain/phone/case_fixture/None/">
                               <data key="case_type" ref="'mother'"/>
                               <data key="case_id" nodeset="instance('selected_cases')/results/value" ref="."/>
                             </query>
                             <instance-datum id="selected_cases" value="$selected_cases"/>
                        </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            self.factory.app.create_suite(),
            "./endpoint",
        )

    def test_shadow_module(self):
        self.shadow_module = self.factory.new_shadow_module('shadow', self.module, with_form=False)
        self.shadow_module.session_endpoint_id = 'my_shadow'

        self.factory.form_requires_case(self.form)

        self.factory.app.rearrange_modules(self.shadow_module.id, 0)

        suite = self.factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
                <endpoint id="my_shadow">
                    <argument id="case_id" />
                    <stack>
                        <push>
                            <datum id="case_id" value="$case_id"/>
                            <command value="'claim_command.my_shadow.case_id'"/>
                        </push>
                        <push>
                            <command value="'m0'"/>
                            <datum id="case_id" value="$case_id"/>
                        </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            suite,
            "./endpoint",
        )
        self.assertXmlPartialEqual(
            """
            <partial>
                <remote-request>
                    <post relevant="count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]) = 0"
                        url="http://localhost:8000/a/test-domain/phone/claim-case/">
                        <data key="case_id" ref="instance('commcaresession')/session/data/case_id"/>
                    </post>
                    <command id="claim_command.my_shadow.case_id">
                        <display>
                            <text/>
                        </display>
                    </command>
                    <instance id="casedb" src="jr://instance/casedb"/>
                    <instance id="commcaresession" src="jr://instance/session"/>
                    <session>
                        <datum function="instance('commcaresession')/session/data/case_id" id="case_id"/>
                    </session>
                    <stack/>
                </remote-request>
            </partial>
            """,
            suite,
            "./remote-request"
        )

        del self.factory.app.modules[0]

    def test_session_endpoint_respect_relevancy_on_followup_form(self):
        self.form.session_endpoint_id = 'my_form'
        self.form.respect_relevancy = False
        self.factory.form_requires_case(self.form, case_type=self.parent_case_type)
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
                <endpoint id="my_form" respect-relevancy="false">
                    <argument id="case_id"/>
                    <stack>
                        <push>
                            <datum id="case_id" value="$case_id"/>
                            <command value="'claim_command.my_form.case_id'"/>
                        </push>
                        <push>
                            <command value="'m0'"/>
                            <datum id="case_id" value="$case_id"/>
                            <command value="'m0-f0'"/>
                        </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            suite,
            "./endpoint",
        )


@patch_validate_xform()
@patch_get_xform_resource_overrides()
@flag_enabled('SESSION_ENDPOINTS')
class SessionEndpointTestsAdvanced(SimpleTestCase, TestXmlMixin):
    file_path = ('data',)

    def setUp(self):
        self.domain = 'test-domain'
        self.factory = AppFactory(build_version='2.51.0', domain=self.domain)
        self.parent_case_type = 'mother'
        self.module, self.form = self.factory.new_advanced_module('advanced', self.parent_case_type)

        builder = XFormBuilder(self.form.name)
        builder.new_question(name='name', label='Name')
        self.form.source = builder.tostring(pretty_print=True).decode('utf-8')

    def test_without_computed(self):
        self.form.session_endpoint_id = 'my_form'
        self.factory.form_requires_case(self.form, case_type=self.parent_case_type)
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_tag="adherence",
            case_type=self.parent_case_type,
            load_case_from_fixture=LoadCaseFromFixture(
                fixture_nodeset="instance('item-list:table_tag')/calendar/year]",
                fixture_tag="selected_date",
                fixture_variable="./@date",
                case_property="adherence_event_date",
                auto_select=True,
                arbitrary_datum_id="extra_id",
                arbitrary_datum_function="extra_function()",
            )
        ))
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
                <endpoint id="my_form">
                    <argument id="case_id_load_mother_0"/>
                    <argument id="selected_date"/>
                    <argument id="adherence"/>
                    <stack>
                        <push>
                          <datum id="case_id_load_mother_0" value="$case_id_load_mother_0"/>
                          <command value="'claim_command.my_form.case_id_load_mother_0'"/>
                        </push>
                        <push>
                          <datum id="selected_date" value="$selected_date"/>
                          <command value="'claim_command.my_form.selected_date'"/>
                        </push>
                        <push>
                          <datum id="adherence" value="$adherence"/>
                          <command value="'claim_command.my_form.adherence'"/>
                        </push>
                        <push>
                            <command value="'m0'"/>
                            <datum id="case_id_load_mother_0" value="$case_id_load_mother_0"/>
                            <datum id="selected_date" value="$selected_date"/>
                            <datum id="adherence" value="$adherence"/>
                            <command value="'m0-f0'"/>
                        </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            suite,
            "./endpoint",
        )

    def test_with_computed(self):
        self.form.session_endpoint_id = 'my_form'
        self.form.function_datum_endpoints = ["extra_id"]
        self.factory.form_requires_case(self.form, case_type=self.parent_case_type)
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_tag="adherence",
            case_type=self.parent_case_type,
            load_case_from_fixture=LoadCaseFromFixture(
                fixture_nodeset="instance('item-list:table_tag')/calendar/year]",
                fixture_tag="selected_date",
                fixture_variable="./@date",
                case_property="adherence_event_date",
                auto_select=True,
                arbitrary_datum_id="extra_id",
                arbitrary_datum_function="extra_function()",
            )
        ))
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
                <endpoint id="my_form">
                    <argument id="case_id_load_mother_0"/>
                    <argument id="extra_id"/>
                    <argument id="selected_date"/>
                    <argument id="adherence"/>
                    <stack>
                        <push>
                          <datum id="case_id_load_mother_0" value="$case_id_load_mother_0"/>
                          <command value="'claim_command.my_form.case_id_load_mother_0'"/>
                        </push>
                        <push>
                          <datum id="selected_date" value="$selected_date"/>
                          <command value="'claim_command.my_form.selected_date'"/>
                        </push>
                        <push>
                          <datum id="adherence" value="$adherence"/>
                          <command value="'claim_command.my_form.adherence'"/>
                        </push>
                        <push>
                            <command value="'m0'"/>
                            <datum id="case_id_load_mother_0" value="$case_id_load_mother_0"/>
                            <datum id="extra_id" value="$extra_id"/>
                            <datum id="selected_date" value="$selected_date"/>
                            <datum id="adherence" value="$adherence"/>
                            <command value="'m0-f0'"/>
                        </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            suite,
            "./endpoint",
        )
