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
        self.case_type = 'patient'
        self.module, self.form = self.factory.new_basic_module('basic', self.case_type)

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
        self.assertXmlPartialEqual(
            """
            <partial>
                <endpoint id="my_form">
                    <stack>
                        <push>
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
        self.factory.form_requires_case(self.form, case_type=self.case_type)
        self.assertXmlPartialEqual(
            """
            <partial>
                <endpoint id="my_form">
                    <argument id="case_id"/>
                    <stack>
                    <push>
                        <command value="'m0-f0'"/>
                        <datum id="case_id" value="$case_id"/>
                    </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            self.factory.app.create_suite(),
            "./endpoint",
        )

    def test_case_list_session_endpoint_id(self):
        self.module.session_endpoint_id = 'my_case_list'
        self.assertXmlPartialEqual(
            """
            <partial>
                <endpoint id="my_case_list">
                    <stack>
                    <push>
                        <command value="'m0-case-list'"/>
                    </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            self.factory.app.create_suite(),
            "./endpoint",
        )
