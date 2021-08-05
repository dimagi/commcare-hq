from mock import patch

from django.test import SimpleTestCase

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
            # TODO: DRY up and/or extract these remote-request snippets?
            """
            <partial>
                <remote-request>
                    <post url="https://www.example.com/a/test-domain/phone/claim-case/"
                          relevant="count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]) = 0">
                        <data key="case_id" ref="instance('commcaresession')/session/data/case_id"/>
                    </post>
                    <command id="claim_command.my_form.case_id">
                        <display>
                            <text>
                                <locale id="case_search.m0"/>
                            </text>
                        </display>
                    </command>
                    <instance id="casedb" src="jr://instance/casedb"/>
                    <instance id="commcaresession" src="jr://instance/session"/>
                    <session>
                        <datum id="case_id" function="instance('commcaresession')/session/data/case_id"/>
                    </session>
                    <stack/>
                </remote-request>
            </partial>
            """,
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
            """
            <partial>
                <remote-request>
                    <post url="https://www.example.com/a/test-domain/phone/claim-case/"
                          relevant="count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/parent_id]) = 0">
                        <data key="case_id" ref="instance('commcaresession')/session/data/parent_id"/>
                    </post>
                    <command id="claim_command.my_form.parent_id">
                        <display>
                            <text>
                                <locale id="case_search.m1"/>
                            </text>
                        </display>
                    </command>
                    <instance id="casedb" src="jr://instance/casedb"/>
                    <instance id="commcaresession" src="jr://instance/session"/>
                    <session>
                        <datum id="parent_id" function="instance('commcaresession')/session/data/parent_id"/>
                    </session>
                    <stack/>
                </remote-request>
                <remote-request>
                    <post url="https://www.example.com/a/test-domain/phone/claim-case/"
                          relevant="count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]) = 0">
                        <data key="case_id" ref="instance('commcaresession')/session/data/case_id"/>
                    </post>
                    <command id="claim_command.my_form.case_id">
                        <display>
                            <text>
                                <locale id="case_search.m1"/>
                            </text>
                        </display>
                    </command>
                    <instance id="casedb" src="jr://instance/casedb"/>
                    <instance id="commcaresession" src="jr://instance/session"/>
                    <session>
                        <datum id="case_id" function="instance('commcaresession')/session/data/case_id"/>
                    </session>
                    <stack/>
                </remote-request>
            </partial>
            """,
            suite,
            "./remote-request",
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
            """
            <partial>
                <remote-request>
                    <post url="https://www.example.com/a/test-domain/phone/claim-case/"
                          relevant="count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/parent_id]) = 0">
                        <data key="case_id" ref="instance('commcaresession')/session/data/parent_id"/>
                    </post>
                    <command id="claim_command.my_child_form.parent_id">
                        <display>
                            <text>
                                <locale id="case_search.m1"/>
                            </text>
                        </display>
                    </command>
                    <instance id="casedb" src="jr://instance/casedb"/>
                    <instance id="commcaresession" src="jr://instance/session"/>
                    <session>
                        <datum id="parent_id" function="instance('commcaresession')/session/data/parent_id"/>
                    </session>
                    <stack/>
                </remote-request>
                <remote-request>
                    <post url="https://www.example.com/a/test-domain/phone/claim-case/"
                          relevant="count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]) = 0">
                        <data key="case_id" ref="instance('commcaresession')/session/data/case_id"/>
                    </post>
                    <command id="claim_command.my_child_form.case_id">
                        <display>
                            <text>
                                <locale id="case_search.m1"/>
                            </text>
                        </display>
                    </command>
                    <instance id="casedb" src="jr://instance/casedb"/>
                    <instance id="commcaresession" src="jr://instance/session"/>
                    <session>
                        <datum id="case_id" function="instance('commcaresession')/session/data/case_id"/>
                    </session>
                    <stack/>
                </remote-request>
            </partial>
            """,
            suite,
            "./remote-request",
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
