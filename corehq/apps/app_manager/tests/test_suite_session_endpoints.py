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
        self.module, self.form = self.factory.new_basic_module('basic', 'patient')

        builder = XFormBuilder(self.form.name)
        builder.new_question(name='name', label='Name')
        self.form.source = builder.tostring(pretty_print=True).decode('utf-8')

    def test_form_session_endpoint_id(self):
        self.form.session_endpoint_id = 'patient_id'
        self.assertXmlPartialEqual(
            """
            <partial>
                <endpoint>
                    <argument id="patient_id"/>
                    <stack>
                    <push>
                        <command value="'m0-f0'"/>
                        <datum id="patient_id" value="instance('commcaresession')/session/data/patient_id"/>
                    </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            self.factory.app.create_suite(),
            "./endpoint",
        )

    def test_case_list_session_endpoint_id(self):
        self.module.session_endpoint_id = 'patient_id'
        self.assertXmlPartialEqual(
            """
            <partial>
                <endpoint>
                    <argument id="patient_id"/>
                    <stack>
                    <push>
                        <command value="'m0-case-list'"/>
                        <datum id="patient_id" value="instance('commcaresession')/session/data/patient_id"/>
                    </push>
                    </stack>
                </endpoint>
            </partial>
            """,
            self.factory.app.create_suite(),
            "./endpoint",
        )
