from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.apps.app_manager.models import Module, Application, CaseSearch, CaseSearchProperty
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    patch_get_xform_resource_overrides,
)
from corehq.apps.builds.models import BuildSpec
from corehq.tests.util.xml import parse_normalize
from corehq.util.test_utils import flag_enabled


@patch_get_xform_resource_overrides()
class SplitScreenCaseSearchTest(SimpleTestCase, SuiteMixin):

    @flag_enabled('SPLIT_SCREEN_CASE_SEARCH')
    def test_split_screen_case_search_removes_search_again(self):
        factory = AppFactory.case_claim_app_factory()
        suite = factory.app.create_suite()
        # case list actions unaffected
        self.assertXmlHasXpath(
            suite,
            "./detail[@id='m0_case_short']/action[display/text/locale[@id='case_search.m0']]"
        )
        self.assertXmlHasXpath(
            suite,
            "./detail[@id='m0_case_short']/action[display/text/locale[@id='case_list_form.m0']]"
        )

        # case search results actions have "search again" removed
        self.assertXmlDoesNotHaveXpath(
            suite,
            "./detail[@id='m0_search_short']/action[display/text/locale[@id='case_search.m0.again']]"
        )
        # non "search again" still present
        self.assertXmlHasXpath(
            suite,
            "./detail[@id='m0_search_short']/action[display/text/locale[@id='case_list_form.m0']]"
        )


@patch_get_xform_resource_overrides()
class DynamicSearchSuiteTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        self.app = Application.new_app("domain", "Untitled Application")
        self.app._id = '123'
        self.app.split_screen_dynamic_search = True
        self.app.build_spec = BuildSpec(version='2.53.0', build_number=1)
        self.module = self.app.add_module(Module.new_module("Followup", None))

        self.module.search_config = CaseSearch(
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
            ],
            search_on_clear=True,
        )

        self.module.assign_references()
        # wrap to have assign_references called
        self.app = Application.wrap(self.app.to_json())
        self.module = self.app.modules[0]

    @flag_enabled('SPLIT_SCREEN_CASE_SEARCH')
    @flag_enabled('DYNAMICALLY_UPDATE_SEARCH_RESULTS')
    def test_dynamic_search_suite(self):
        suite = self.app.create_suite()
        suite = parse_normalize(suite, to_string=False)
        self.assertEqual("true", suite.xpath("./remote-request[1]/session/query/@dynamic_search")[0])

    @patch('corehq.apps.app_manager.models.ModuleBase.is_auto_select', return_value=True)
    @flag_enabled('SPLIT_SCREEN_CASE_SEARCH')
    @flag_enabled('DYNAMICALLY_UPDATE_SEARCH_RESULTS')
    def test_dynamic_search_suite_disable_with_auto_select(self, mock):
        suite = self.app.create_suite()
        suite = parse_normalize(suite, to_string=False)
        self.assertEqual(True, self.module.is_auto_select())
        self.assertEqual("false", suite.xpath("./remote-request[1]/session/query/@dynamic_search")[0])

    @flag_enabled('SPLIT_SCREEN_CASE_SEARCH')
    def test_search_on_clear(self):
        suite = self.app.create_suite()
        suite = parse_normalize(suite, to_string=False)
        self.assertEqual("true", suite.xpath("./remote-request[1]/session/query/@search_on_clear")[0])

    @patch('corehq.apps.app_manager.models.ModuleBase.is_auto_select', return_value=True)
    @flag_enabled('SPLIT_SCREEN_CASE_SEARCH')
    def test_search_on_clear_disable_with_auto_select(self, mock):
        suite = self.app.create_suite()
        suite = parse_normalize(suite, to_string=False)
        self.assertEqual(True, self.module.is_auto_select())
        self.assertEqual("false", suite.xpath("./remote-request[1]/session/query/@search_on_clear")[0])
