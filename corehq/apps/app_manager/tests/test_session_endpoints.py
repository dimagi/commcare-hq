from unittest.mock import patch

from django.test import TestCase

from corehq import toggles
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.xform_builder import XFormBuilder


class SessionEndpointTests(TestCase):

    def setUp(self):
        self.domain = 'test-domain'
        toggles.SESSION_ENDPOINTS.set(self.domain, True, toggles.NAMESPACE_DOMAIN)
        self.factory = AppFactory(build_version='2.51.0', domain=self.domain)
        self.module, self.form = self.factory.new_basic_module('basic', 'patient')

        builder = XFormBuilder(self.form.name)
        builder.new_question(name='name', label='Name')
        self.form.source = builder.tostring(pretty_print=True).decode('utf-8')

    def tearDown(self):
        toggles.SESSION_ENDPOINTS.set(self.domain, False, toggles.NAMESPACE_DOMAIN)

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_form_session_endpoint_id(self, mock):
        endpoint_xml = b"""
  <endpoint>
    <argument id="patient_id"/>
    <stack>
      <push>
        <command value="'m0-f0'"/>
        <datum id="patient_id" value="instance('commcaresession')/session/data/patient_id"/>
      </push>
    </stack>
  </endpoint>"""
        self.form.session_endpoint_ids = ['patient_id']
        files = self.factory.app.create_all_files()
        self.assertIn(endpoint_xml, files['suite.xml'])

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_case_list_session_endpoint_id(self, mock):
        endpoint_xml = b"""
  <endpoint>
    <argument id="patient_id"/>
    <stack>
      <push>
        <command value="'m0-case-list'"/>
        <datum id="patient_id" value="instance('commcaresession')/session/data/patient_id"/>
      </push>
    </stack>
  </endpoint>"""
        self.module.session_endpoint_ids = ['patient_id']
        files = self.factory.app.create_all_files()
        self.assertIn(endpoint_xml, files['suite.xml'])
