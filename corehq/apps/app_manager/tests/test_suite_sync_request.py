from django.test import SimpleTestCase
from mock import patch

from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module, CaseSearch, CaseSearchProperty
from corehq.apps.app_manager.tests import TestXmlMixin, SuiteMixin


DOMAIN = 'test_domain'


class SyncRequestSuiteTest(SimpleTestCase, TestXmlMixin, SuiteMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        self.app = Application.new_app(DOMAIN, "Untitled Application", application_version=APP_V2)
        self.module = self.app.add_module(Module.new_module("Untitled Module", None))
        self.app.new_form(0, "Untitled Form", None)
        self.module.case_type = 'case'

    def test_sync_request(self):
        """
        Suite should include sync-request if searching is configured
        """
        self.module.search_config = CaseSearch(
            command_label={'en': 'Search Patients Nationally'},
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
                CaseSearchProperty(name='dob', label={'en': 'Date of birth'})
            ]
        )
        with patch('corehq.util.view_utils.get_url_base') as get_url_base_patch:
            get_url_base_patch.return_value = 'https://www.example.com'
            suite = self.app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('sync_request'), suite, "./sync-request[1]")

    def test_case_search_action(self):
        """
        Case search action should be added to case list
        """
        self.assertTrue(False)  # TODO: Write this test
